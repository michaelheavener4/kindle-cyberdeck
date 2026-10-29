"""JSON-lines worker around the installed Nicotine+ protocol engine.

Only the worker's main thread calls Nicotine. No shell commands or filenames
are executed from peer metadata. Its separate profile has no shared folders.
"""
import configparser
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

FORMATS = {".epub", ".azw3", ".mobi", ".pdf", ".txt", ".fb2", ".rtf"}


def run(state_dir):
    from pynicotine.i18n import apply_translations
    apply_translations()
    from pynicotine.config import config
    from pynicotine.core import core
    from pynicotine.events import events
    from pynicotine.transfers import TransferStatus

    os.umask(0o077)
    state = Path(state_dir)
    profile = state / "nicotine"
    profile.mkdir(parents=True, exist_ok=True)
    profile.chmod(0o700)
    source = configparser.ConfigParser(interpolation=None)
    source.read(Path.home() / ".config/nicotine/config")
    credentials = source["server"] if source.has_section("server") else {}
    if not credentials.get("login") or not credentials.get("passw"):
        raise RuntimeError("Set up your Soulseek login in Nicotine+ first.")

    config.set_config_file(str(profile / "config"))
    config.set_data_folder(str(profile))
    config.load_config(isolated_mode=True)
    config.sections["server"].update(
        login=credentials["login"], passw=credentials["passw"],
        auto_connect_startup=False, autojoin=[], upnp=False,
        portrange=(2235, 2235),
    )
    config.sections["transfers"].update(
        downloaddir=str(state / "downloads"),
        incompletedir=str(state / "incomplete"),
        shared=[], buddyshared=[], trustedshared=[],
        afterfinish="", afterfolder="", autoclear_downloads=False,
        enablefilters=False,
    )
    config.sections["plugins"].update(enable=False, enabled=[])
    for key in config.sections["notifications"]:
        if key.startswith("notification_popup"):
            config.sections["notifications"][key] = False

    components = {
        "signal_handler", "network_thread", "shares", "users", "notifications",
        "network_filter", "statistics", "search", "downloads", "uploads",
        "interests", "userbrowse", "userinfo", "buddies", "chatrooms",
        "privatechat", "pluginhandler",
    }
    core.init_components(components, isolated_mode=True)
    results = {}
    login_error = []

    def response(msg):
        if msg.token not in results or not msg.list:
            return
        found = results[msg.token]
        for _code, name, size, _ext, attrs in msg.list:
            if Path(name.replace("\\", "/")).suffix.lower() not in FORMATS:
                continue
            if not isinstance(size, int) or not 0 < size <= 100 * 1024 * 1024:
                continue
            if not isinstance(name, str) or len(name) > 4096:
                continue
            key = (msg.username, name)
            if key in found or len(found) >= 1000:
                continue
            found[key] = dict(
                username=msg.username, filename=name, size=size,
                free=bool(msg.freeulslots), speed=msg.ulspeed or 0,
                queue=msg.inqueue or 0, attributes=attrs or {},
            )

    events.connect("file-search-response", response)
    events.connect("invalid-password", lambda: login_error.append("Soulseek rejected the saved login."))
    events.connect("invalid-username", lambda: login_error.append("Soulseek rejected the saved username."))

    def handle(request):
        try:
            op = request.get("op")
            if op == "status":
                value = {"connected": core.users.login_status != 0, "error": login_error[-1:]}
            elif op == "search":
                query = request["query"]
                if not isinstance(query, str) or not 2 <= len(query) <= 250:
                    raise ValueError("Search for a book title or author.")
                if core.users.login_status == 0:
                    raise ValueError("Soulseek is not connected yet.")
                core.search.do_search(query, "global", switch_page=False)
                token = core.search.token
                results[token] = {}
                value = {"token": token}
            elif op == "results":
                value = list(results.get(int(request["token"]), {}).values())
            elif op == "end_search":
                token = int(request["token"])
                core.search.remove_search(token)
                results.pop(token, None)
                value = True
            elif op == "download":
                item = request["item"]
                username, filename, size = item["username"], item["filename"], item["size"]
                if not isinstance(username, str) or len(username) > 100:
                    raise ValueError("Invalid peer name.")
                if not isinstance(filename, str) or len(filename) > 4096:
                    raise ValueError("Invalid remote filename.")
                if Path(filename.replace("\\", "/")).suffix.lower() not in FORMATS:
                    raise ValueError("That is not a supported book format.")
                if not isinstance(size, int) or not 0 < size <= 100 * 1024 * 1024:
                    raise ValueError("Book size must be below 100 MB.")
                key = hashlib.sha256((username + "\0" + filename).encode()).hexdigest()[:20]
                folder = state / "downloads" / key
                folder.mkdir(parents=True, exist_ok=True)
                attrs = {int(k): v for k, v in item.get("attributes", {}).items()}
                transfer = core.downloads.transfers.get(username + filename)
                if transfer is not None and transfer.status != TransferStatus.FINISHED:
                    core.downloads.retry_download(transfer)
                else:
                    core.downloads.enqueue_download(username, filename, str(folder), size, attrs)
                value = {"key": key}
            elif op == "transfer":
                item = request["item"]
                transfer = core.downloads.transfers.get(item["username"] + item["filename"])
                if transfer is None:
                    value = {"status": "Missing"}
                else:
                    done = transfer.status == TransferStatus.FINISHED
                    path = core.downloads.get_current_download_file_path(transfer) if done else None
                    value = {"status": transfer.status, "bytes": transfer.current_byte_offset or 0,
                             "size": transfer.size, "queue": transfer.queue_position,
                             "finished": done, "path": path}
            elif op == "quit":
                value = True
                events.schedule(0.1, core.quit)
            else:
                raise ValueError("Unknown Soulseek operation.")
            reply = {"id": request.get("id"), "result": value}
        except Exception as exc:
            reply = {"id": request.get("id"), "error": str(exc)}
        print(json.dumps(reply), flush=True)

    def read_requests():
        for line in sys.stdin:
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    continue
            except (ValueError, TypeError):
                continue
            events.invoke_main_thread(handle, request)
        events.invoke_main_thread(core.quit)

    core.start()
    core.connect()
    threading.Thread(target=read_requests, daemon=True).start()
    while events.process_thread_events():
        time.sleep(0.05)


if __name__ == "__main__":
    run(sys.argv[1])
