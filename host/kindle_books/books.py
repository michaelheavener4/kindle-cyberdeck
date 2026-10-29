"""Local chat, Soulseek acquisition, Calibre conversion, and Kindle delivery."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import queue
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import uuid
import zipfile

from . import covers

STATE = Path.home() / ".local/share/kindle-books"
KINDLE = "root@kindle.example.invalid"
BOOK_DIR = "/mnt/kindle/documents/Books"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", KINDLE]
DIRECT = {".azw3", ".mobi"}
FORMATS = DIRECT | {".pdf", ".epub", ".txt", ".fb2", ".rtf", ".docx"}


def clean(text):
    return "".join(c for c in str(text) if not unicodedata.category(c).startswith("C"))[:350]


def words(text):
    return set(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold()))


def display_name(item):
    return clean(item["filename"].replace("\\", "/").rsplit("/", 1)[-1])


def library_title(filename):
    title = Path(filename).stem
    title = re.sub(r"(?:_|-)[0-9a-fA-F]{8,40}$", "", title)
    title = re.sub(r"_[A-Z0-9]{20,40}$", "", title)
    title = re.sub(r"_B[A-Z0-9]{9}$", "", title)
    return clean(title.replace("_", ": "))


def item_id(item):
    return hashlib.sha256((item["username"] + "\0" + item["filename"]).encode()).hexdigest()[:20]


def rank(items, title, author=""):
    title_words = words(title) - {"the", "a", "an", "and", "of", "by"}
    author_words = words(author)
    ranked = []
    for item in items:
        ext = PurePosixPath(item["filename"].replace("\\", "/")).suffix.lower()
        if ext not in FORMATS or not 0 < item["size"] <= 100 * 1024 * 1024:
            continue
        tokens = words(item["filename"])
        coverage = len(title_words & tokens) / max(1, len(title_words))
        author_match = len(author_words & tokens) / max(1, len(author_words))
        if title_words and coverage < 0.5:
            continue
        score = coverage * 100 + author_match * 20
        score += {".epub": 18, ".azw3": 16, ".mobi": 10, ".pdf": 2}.get(ext, 0)
        score += 6 if item.get("free") else 0
        score += min(3, item.get("speed", 0) / 1_000_000)
        score -= min(10, item.get("queue", 0) / 10)
        ranked.append((score, dict(item, title_coverage=coverage, author_coverage=author_match)))
    distinct = []
    seen = set()
    for _score, item in sorted(ranked, key=lambda x: x[0], reverse=True):
        key = (tuple(sorted(words(display_name(item)))), item["size"])
        if key not in seen:
            seen.add(key)
            distinct.append(item)
    # Keep the best EPUB choices, while making other available formats visible.
    choices = distinct[:5]
    present = {Path(item["filename"]).suffix.lower() for item in choices}
    for ext in [".azw3", ".mobi", ".pdf"]:
        if ext not in present:
            alternative = next((item for item in distinct if Path(item["filename"]).suffix.lower() == ext), None)
            if alternative:
                choices.append(alternative)
    choices.extend(item for item in distinct if item not in choices)
    return choices[:15]


class Soulseek:
    def __init__(self):
        self.guard = open(STATE / "session.lock", "a")
        try:
            fcntl.flock(self.guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.guard.close()
            raise RuntimeError("Books is already open. Return to its existing session.") from exc
        self.pending = {}
        self.lock = threading.Lock()
        self.serial = 0
        self.log = open(STATE / "soulseek.log", "a", buffering=1)
        self.process = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("soulseek.py")), str(STATE)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
            text=True, bufsize=1,
        )
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.process.stdout:
            try:
                value = json.loads(line)
            except ValueError:
                continue
            with self.lock:
                target = self.pending.get(value.get("id"))
            if target:
                target.put(value)
        with self.lock:
            for target in self.pending.values():
                target.put({"error": "Soulseek stopped. See ~/.local/share/kindle-books/soulseek.log."})

    def call(self, op, timeout=15, **kwargs):
        target = queue.Queue()
        with self.lock:
            if self.process.poll() is not None:
                raise RuntimeError("Soulseek is not running. Reopen Books to reconnect.")
            self.serial += 1
            serial = self.serial
            self.pending[serial] = target
            self.process.stdin.write(json.dumps(dict(id=serial, op=op, **kwargs)) + "\n")
            self.process.stdin.flush()
        try:
            value = target.get(timeout=timeout)
            if "error" in value:
                raise RuntimeError(value["error"])
            return value["result"]
        except queue.Empty as exc:
            raise RuntimeError("Soulseek is taking too long to respond.") from exc
        finally:
            with self.lock:
                self.pending.pop(serial, None)

    def connect(self):
        for _ in range(45):
            value = self.call("status")
            if value["connected"]:
                return
            if value.get("error"):
                raise RuntimeError(value["error"][-1])
            time.sleep(1)
        raise RuntimeError("Could not connect to Soulseek. Check Nicotine+ and the network.")

    def search(self, query, seconds=18):
        token = self.call("search", query=query)["token"]
        try:
            time.sleep(seconds)
            return self.call("results", token=token)
        finally:
            self.call("end_search", token=token)

    def close(self):
        if self.process.poll() is None:
            try:
                self.call("quit", timeout=3)
                self.process.wait(timeout=5)
            except (RuntimeError, subprocess.TimeoutExpired):
                self.process.terminate()
        self.log.close()
        self.guard.close()


SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "action": {"type": "string", "enum": ["search", "status", "library", "help", "chat", "exit"]},
        "title": {"type": "string"}, "author": {"type": "string"},
        "query": {"type": "string"}, "reply": {"type": "string"},
    },
    "required": ["action", "title", "author", "query", "reply"],
}


def intent(text, history):
    prompt = (
        "You parse user requests for a Kindle book assistant. Return only the requested JSON. "
        "Do not use tools, inspect files, or run commands. You only interpret the supplied conversation. "
        "For a specific requested book, action=search with its title, author if given, and a short "
        "Soulseek search query containing distinctive title and author words, without quotes or formats. "
        "Do not invent a book or author. If unclear, action=chat and ask a concise clarification. "
        "Use conversation context for corrections and 'another by that author'. "
        "Status, library, help, and exit map to their respective actions. "
        "Reply briefly in first person; never claim a search, download, or delivery already happened.\n"
        + json.dumps({"recent_conversation": history[-6:], "user_message": text}, ensure_ascii=False)
    )
    with tempfile.TemporaryDirectory(prefix="intent-", dir=STATE) as folder:
        folder = Path(folder)
        schema = folder / "schema.json"
        output = folder / "intent.json"
        schema.write_text(json.dumps(SCHEMA))
        cmd = [
            "codex", "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
            "--sandbox", "read-only", "--color", "never", "--cd", str(folder),
            "-c", 'model_reasoning_effort="low"', "-c", 'web_search="disabled"',
            "--output-schema", str(schema), "--output-last-message", str(output), "-",
        ]
        result = subprocess.run(cmd, input=prompt, text=True, capture_output=True, timeout=90)
        if result.returncode or not output.exists():
            raise RuntimeError("The AI session is unavailable. Check `codex login status` on Omarchy.")
        value = json.loads(output.read_text())
        if value.get("action") not in SCHEMA["properties"]["action"]["enum"]:
            raise RuntimeError("The AI returned an invalid request. Please rephrase it.")
        if any(not isinstance(value.get(k), str) or len(value[k]) > 1000 for k in SCHEMA["required"]):
            raise RuntimeError("The AI returned an invalid request. Please rephrase it.")
        return value


def validate_book(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 100 * 1024 * 1024:
        raise ValueError("The download is not a complete supported book file.")
    suffix = path.suffix.lower()
    if suffix not in FORMATS:
        raise ValueError("Unsupported book format.")
    if suffix == ".epub":
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > 10000 or sum(x.file_size for x in entries) > 250 * 1024 * 1024:
                raise ValueError("This EPUB expands beyond the size limit.")
            for entry in entries:
                name = PurePosixPath(entry.filename)
                if name.is_absolute() or ".." in name.parts or stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError("This EPUB contains unsafe paths.")
            if archive.read("mimetype").strip() != b"application/epub+zip":
                raise ValueError("This download is not a valid EPUB.")
    elif suffix == ".pdf":
        with path.open("rb") as f:
            if not f.read(1024).lstrip().startswith(b"%PDF-"):
                raise ValueError("This download is not a valid PDF.")


def prepare_book(source, title, author):
    source = Path(source)
    validate_book(source)
    cover = covers.ensure(source, title, author, STATE / "covers")
    digest = hashlib.sha256(source.read_bytes() + cover.read_bytes() + title.encode() + author.encode()).hexdigest()[:16]
    folder = STATE / "converted"
    folder.mkdir(exist_ok=True)
    extension = source.suffix.lower() if source.suffix.lower() in DIRECT else ".azw3"
    destination = folder / (digest + extension)
    if destination.exists() and destination.stat().st_size:
        return destination
    temporary = folder / (digest + ".partial" + extension)
    if source.suffix.lower() in DIRECT:
        shutil.copy2(source, temporary)
        command = ["ebook-meta", str(temporary), "--cover", str(cover)]
    else:
        command = ["ebook-convert", str(source), str(temporary), "--cover", str(cover)]
    if title:
        command += ["--title", title]
    if author:
        command += ["--authors", author]
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=240)
    if result.returncode or not temporary.exists() or not temporary.stat().st_size:
        raise RuntimeError("Calibre could not convert this book. Try another copy or format.")
    check = folder / (digest + ".cover-check.jpg")
    result = subprocess.run(["ebook-meta", str(temporary), "--get-cover", str(check)],
                            capture_output=True, text=True, timeout=45)
    if result.returncode or not covers.usable(check):
        raise RuntimeError("The Kindle book did not retain a usable cover.")
    temporary.replace(destination)
    return destination


def deliver_book(path, title, author, existing_name=None):
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    label = " - ".join(x for x in [title, author] if x) or path.stem
    label = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    label = re.sub(r"[^a-zA-Z0-9 ._-]", "", label).strip(" .")[:110] or "Book"
    filename = label + "-" + digest[:8] + path.suffix.lower()
    if existing_name:
        if not re.fullmatch(r"[a-zA-Z0-9 ._-]{1,160}", existing_name) or "/" in existing_name or existing_name.startswith("."):
            raise ValueError("Unexpected managed Kindle filename.")
        filename = existing_name
    final = BOOK_DIR + "/" + filename
    temporary = BOOK_DIR + "/." + filename + ".partial-" + uuid.uuid4().hex[:8]
    command = "mkdir -p " + shlex.quote(BOOK_DIR) + " && cat > " + shlex.quote(temporary)
    command += " && sha256sum " + shlex.quote(temporary)
    with path.open("rb") as data:
        result = subprocess.run(SSH + [command], stdin=data, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise ConnectionError("Kindle is offline. I will send the book when Linux is reachable again.")
    if not result.stdout.split() or result.stdout.split()[0] != digest:
        raise RuntimeError("The Kindle copy did not pass its checksum check.")
    result = subprocess.run(SSH + ["mv " + shlex.quote(temporary) + " " + shlex.quote(final)],
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise ConnectionError("Could not finish the Kindle transfer; the local book is kept.")
    install_thumbnail(path, title, author)
    return filename


def install_thumbnail(path, title, author):
    # Use Calibre's device logic for the embedded UUID/content-type naming.
    code = ("import sys; from calibre.devices.kindle.driver import thumbnail_filename; "
            "f=open(sys.argv[1],'rb'); print(thumbnail_filename(f)); f.close()")
    result = subprocess.run(["calibre-debug", "-c", code, str(path)],
                            capture_output=True, text=True, timeout=30)
    names = [s.strip() for s in result.stdout.splitlines()
             if re.fullmatch(r"thumbnail_[A-Za-z0-9_.-]+_portrait\.jpg", s.strip())]
    if result.returncode or not names:
        raise RuntimeError("Book copied, but Calibre could not identify its Kindle cover thumbnail.")
    name = names[-1]
    cover = covers.ensure(path, title, author, STATE / "covers")
    from PIL import Image
    with Image.open(cover) as image:
        image = image.convert("RGB")
        image.thumbnail((500, 500))
        buffer = __import__("io").BytesIO()
        image.save(buffer, "JPEG", quality=94)
    data = buffer.getvalue()
    main = "/mnt/kindle/system/thumbnails/" + name
    cache = "/mnt/kindle/amazon-cover-bug/" + name
    temporary = main + ".books-partial"
    cmd = "mkdir -p /mnt/kindle/system/thumbnails /mnt/kindle/amazon-cover-bug"
    cmd += " && cat > " + shlex.quote(temporary)
    cmd += " && cp " + shlex.quote(temporary) + " " + shlex.quote(cache)
    cmd += " && mv " + shlex.quote(temporary) + " " + shlex.quote(main)
    cmd += " && sha256sum " + shlex.quote(main)
    result = subprocess.run(SSH + [cmd], input=data, capture_output=True, timeout=30)
    if result.returncode or not result.stdout.split() or result.stdout.split()[0].decode() != hashlib.sha256(data).hexdigest():
        raise ConnectionError("The book is copied; waiting to finish its Kindle cover thumbnail.")


def kindle_library():
    code = '''import json, os, re
root='/mnt/kindle/documents'
extensions={'.azw3','.azw','.mobi','.kfx','.pdf','.txt','.prc','.epub'}
books=[]
for folder,dirs,files in os.walk(root):
 dirs[:]=[d for d in dirs if not d.startswith('.') and not d.endswith('.sdr')]
 for name in files:
  if os.path.splitext(name)[1].lower() not in extensions: continue
  if name in {'JAILBROKEN.txt','fontcal.azw3'} or re.fullmatch(r'pw[0-9].*-jb\\.azw3|[A-Z][a-z]{2}_[0-9]{2}_.*\\.txt',name): continue
  path=os.path.join(folder,name)
  if os.path.islink(path): continue
  try:
   info=os.stat(path)
   books.append(dict(name=name,path=os.path.relpath(path,root),size=info.st_size))
  except OSError: pass
print(json.dumps(sorted(books,key=lambda b:b['name'].casefold())))'''
    command = "python3 -c " + shlex.quote(code)
    result = subprocess.run(SSH + [command], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ConnectionError("Kindle is unreachable. Open Linux on it to view its books.")
    return json.loads(result.stdout)


class Jobs:
    def __init__(self, client, announce=print):
        self.client = client
        self.announce = announce
        self.lock = threading.RLock()
        self.path = STATE / "jobs.json"
        self.jobs = json.loads(self.path.read_text()) if self.path.exists() else []
        self.stop = threading.Event()
        for job in self.jobs:
            if job["state"] == "downloading":
                client.call("download", item=job["item"])
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()

    def save(self):
        with self.lock:
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.jobs, ensure_ascii=False, indent=2))
            temporary.replace(self.path)

    def add(self, item, title, author):
        key = item_id(item)
        with self.lock:
            if any(j["id"] == key and j["state"] != "error" for j in self.jobs):
                return "That copy is already in your book list. Type status or library."
            self.client.call("download", item=item)
            self.jobs.append(dict(id=key, item=item, title=title, author=author,
                                  state="downloading", progress="Queued", created=time.time()))
            self.save()
        return "I’m downloading it. I’ll send it to the Kindle when it’s complete."

    def _monitor(self):
        while not self.stop.wait(2):
            with self.lock:
                pending = [j for j in self.jobs if j["state"] not in {"sent", "error"}]
            for job in pending:
                if self.stop.is_set():
                    return
                try:
                    if job["state"] == "downloading":
                        transfer = self.client.call("transfer", item=job["item"])
                        if transfer["status"] == "Missing":
                            self.client.call("download", item=job["item"])
                            continue
                        job["progress"] = transfer["status"]
                        if transfer.get("size"):
                            job["progress"] += " " + str(int(100 * transfer.get("bytes", 0) / transfer["size"])) + "%"
                        if not transfer.get("finished"):
                            continue
                        source = Path(transfer["path"])
                        root = (STATE / "downloads").resolve()
                        if source.is_symlink() or not source.resolve().is_relative_to(root):
                            raise ValueError("The completed download has an unexpected location.")
                        job.update(state="converting", source=str(source), progress="Converting for Kindle")
                        self.save()
                    if job["state"] == "converting":
                        prepared = prepare_book(job["source"], job["title"], job["author"])
                        job.update(state="ready", prepared=str(prepared), progress="Ready to send")
                        self.save()
                    if job["state"] == "ready":
                        if time.time() < job.get("retry_at", 0):
                            continue
                        filename = deliver_book(job["prepared"], job["title"], job["author"])
                        job.update(state="sent", kindle_file=filename, progress="On your Kindle")
                        self.save()
                        self.announce("\nBooks: Sent “" + clean(job["title"]) + "” to your Kindle. Exit Linux to read it in Library.")
                except ConnectionError:
                    job.update(state="ready", retry_at=time.time() + 30, progress="Waiting for Kindle")
                    self.save()
                except Exception as exc:
                    job.update(state="error", progress=clean(exc))
                    self.save()
                    self.announce("\nBooks: “" + clean(job["title"]) + "”: " + clean(exc))

    def listing(self, sent_only=False):
        with self.lock:
            rows = [j for j in self.jobs if not sent_only or j["state"] == "sent"]
            return [(clean(j["title"]), clean(j["progress"])) for j in rows[-15:]]

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)
        self.save()


HELP = "Tell me a book title and author, then choose from the results. I’ll add a cover and send it to your Kindle.\nType library, status, results, or quit. Keep this session open while downloads finish."


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cyberdeck Books")
    parser.add_argument("--search", help="Test a Soulseek search without AI or downloading")
    parser.add_argument("--seconds", type=int, default=18)
    parser.add_argument("--send", type=Path, help="Convert and send a local book")
    parser.add_argument("--title", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--intent", help="Test the AI book-request parser")
    parser.add_argument("--library", action="store_true", help="List books actually stored on the Kindle")
    args = parser.parse_args(argv)
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True)
    STATE.chmod(0o700)
    if args.library:
        print(json.dumps(kindle_library(), ensure_ascii=False, indent=2))
        return 0
    if args.intent:
        print(json.dumps(intent(args.intent, []), ensure_ascii=False))
        return 0
    if args.send:
        ready = prepare_book(args.send, args.title, args.author)
        filename = deliver_book(ready, args.title, args.author)
        print("Sent to Kindle: " + filename)
        return 0
    print("BOOKS\n\n  1  Find a book\n  2  On my Kindle\n  3  Downloads\n  0  Back\n", flush=True)
    client = None
    jobs = None
    try:
        client = Soulseek()
        if args.search:
            client.connect()
            print(json.dumps(client.search(args.search, max(1, min(60, args.seconds))), ensure_ascii=False))
            return 0
        jobs = Jobs(client)
        print(HELP)
        history = []
        matches = []
        last_title = last_author = ""
        while True:
            try:
                text = input("\nYou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text:
                continue
            lowered = text.casefold()
            selected = re.fullmatch(r"(?:pick|choose|download|get)\s+(\d+)", lowered)
            if selected:
                text = selected.group(1)
                lowered = text
            if lowered in {"quit", "exit", "/quit", "0"}:
                break
            if lowered in {"help", "/help"}:
                print("Books: " + HELP)
                continue
            if text == "1" and not matches:
                print("Books: What would you like to read? Give me the title and author.")
                matches = []
                continue
            if text == "2" and not matches:
                lowered = "library"
            if text == "3" and not matches:
                lowered = "status"
            if lowered in {"status", "library", "results"}:
                action = lowered
            elif lowered.startswith("search "):
                value = dict(action="search", title=text[7:], author="", query=text[7:], reply="")
                action = "search"
            elif text.isdecimal() and matches:
                n = int(text)
                if 1 <= n <= len(matches):
                    print("Books: " + jobs.add(matches[n - 1], last_title, last_author))
                else:
                    print("Books: Choose a number from the results.")
                continue
            else:
                print("Books: Let me check that request…", flush=True)
                try:
                    value = intent(text[:1000], history)
                except (RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
                    print("Books: " + clean(exc) + " You can also type: search TITLE AUTHOR")
                    if not lowered.startswith("search "):
                        continue
                    value = dict(action="search", title=text[7:], author="", query=text[7:], reply="")
                history += [{"user": text}, {"assistant": value}]
                action = value["action"]
                if value.get("reply"):
                    print("Books: " + clean(value["reply"]))
            if action == "exit":
                break
            if action == "library":
                try:
                    rows = kindle_library()
                    print("Books: On your Kindle (" + str(len(rows)) + "):")
                    for n, row in enumerate(rows, 1):
                        title = library_title(row["name"])
                        if len(title) > 67:
                            title = title[:64].rstrip() + "..."
                        print(str(n) + ". " + title + "  [" + Path(row["name"]).suffix[1:].upper() + "]")
                    if not rows:
                        print("No book files found in documents yet.")
                    print("Exit Linux to open these in the Kindle Library.")
                except (ConnectionError, ValueError) as exc:
                    print("Books: " + clean(exc))
                matches = []
            elif action == "status":
                rows = jobs.listing()
                print("Books: " + ("\n".join(t + " — " + s for t, s in rows) if rows else "No books yet."))
            elif action == "help":
                print("Books: " + HELP)
            elif action == "results":
                for n, item in enumerate(matches[:8], 1):
                    print(str(n) + ". " + display_name(item))
            elif action == "search":
                query_text = value["query"].strip()[:250]
                if len(query_text) < 2:
                    print("Books: Which title or author should I search for?")
                    continue
                last_title, last_author = value["title"] or query_text, value["author"]
                print("Books: Searching Soulseek for " + clean(query_text) + "…", flush=True)
                try:
                    client.connect()
                    matches = rank(client.search(query_text), last_title, last_author)
                except RuntimeError as exc:
                    print("Books: " + clean(exc))
                    continue
                if not matches:
                    print("Books: No matching book files came back. Try a shorter title or another spelling.")
                    continue
                print("Books: Choose a result number to download, or rephrase your request:")
                for n, item in enumerate(matches[:8], 1):
                    ext = Path(item["filename"]).suffix[1:].upper()
                    size = f"{item['size'] / 1024:.0f} KB"
                    availability = "ready" if item.get("free") else "queued"
                    print(str(n) + ". " + display_name(item))
                    print("   " + ext + " · " + size + " · " + availability)
        if jobs and any(s not in {"On your Kindle"} for _t, s in jobs.listing()):
            print("Pending books are saved. Reopen Books to resume them.")
        return 0
    except (RuntimeError, OSError) as exc:
        print("Books: " + clean(exc), file=sys.stderr)
        return 1
    finally:
        if jobs:
            jobs.close()
        if client:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
