# Resume: Kindle cyberdeck instrument panel

Checkpoint: 2026-10-26, about 15:23 America/Los_Angeles. User says Omarchy is updating and asks to preserve the work in case a restart interrupts it. This is not a request to abandon or pause the task.

## User intent

Build the cyberdeck instrument panel on the jailbroken Kindle Alpine/JWM environment. It should look like a monochrome cyberpunk/netrunner tablet. User tried the first installed version and reported that tapping Mac or Kindle did not switch the selected node. They specifically requested a cool current-time clock at the upper right and a stronger cyberpunk visual treatment.

## Current implementation and state

Source root: `/home/zephyrillius/Projects/kindle-cyberdeck` (not a git repository).

- `overlay/usr/local/bin/deck-instruments`: native Python GTK3/Cairo app, unique application ID `org.cyberdeck.Instruments`. Three-machine diagram; selected-machine load, RAM, storage, uptime, battery, watched processes, loaded Ollama models, FM CLI presence, persistent tmux sessions, and host job counts. Explicit buttons open existing shell/Codex/OpenCode/Mac FM/local AI/screen helpers.
- `overlay/usr/local/bin/deck-instrument-probe`: stdlib-only read-only Linux/macOS telemetry. Passed over SSH stdin to existing `omarchy` and `mac` aliases; no remote service installation. Only GET /api/ps for Ollama; no inference or model loading.
- Home and Dev menu entries added in `deck-home-ui`, plus Dev → t in `cyberdeck`.
- Both new scripts and both menu files are installed in `/usr/local/bin/` and persistent `/mnt/kindle/linux/bin/` on Kindle. Backup: `/mnt/kindle/linux/backups/instruments-20261026-220908/`.
- First version was opened and collected real data for all three nodes. GUI cache `/home/alpine/.cache/kindle-instruments/snapshot.json` confirmed Kindle, Omarchy, Mac all online. Mac Ollama online, zero models loaded. User completed a Tailscale SSH check for Kindle → Omarchy during this task.
- Existing panel process last observed PID **29004**, `/usr/bin/python3 /usr/local/bin/deck-instruments`. It is still running the OLD UI unless a later step relaunches it. Verify PID/argv before terminating anything. Stop only the panel, never JWM, tailscaled, chess, native framework, etc.

## Latest revision: written and installed, not yet physically verified

- Replaced custom DrawingArea release-event hit testing with real GTK buttons in a Gtk.Overlay/Gtk.Grid layer. The wire drawing remains Cairo; actual node interaction now uses stock Gtk.Button clicked signals.
- Clock at upper right: white seven-segment digits on black, date and timezone. Default America/Los_Angeles with IANA DST; explicit UTC fallback if zoneinfo unavailable. Updates at most once per minute while active; no flashing seconds.
- More industrial visual treatment: header, MK.06 markings, black selected-machine band, outlined meter panels, uppercase controls, event-buffer labels.
- Clock preview saved durably in `build/instruments/kindle-instruments-clock.png`; initial schematic preview also in that folder.
- New UI code has been compiled, copied to BOTH live and persistent Kindle paths. It has NOT replaced the live process yet. This is the main remaining step after tests.

## Validation

- Latest full unit suite: **58 tests pass** (`python3 -m unittest discover -s host/tests -q` from project root).
- Covers telemetry parsing including Mac page sizes, model GET-only reads, host alias allowlist, no unrelated process info, auth/offline distinction, last-good data preservation, quiet event logging, pause/inactive polling, timezone/DST, diagram geometry, and bounded SSH probe construction.
- FIRST UI version passed on-device isolated GTK geometry tests for all three nodes in portrait, landscape, and keyboard-reduced dimensions; shell action and Pause tested.
- The native UI test has now been updated for the NEW real node buttons and clock. **Run it again before declaring the touch fix complete.** File: `host/tests/check_instruments_ui.py`. It uses a distinct application ID `.Check`, a fake collector, no real tools/model calls, and no screenshots.

## Next steps

1. Check SSH: `ssh -o ConnectTimeout=6 root@kindle.example.invalid 'pidof jwm'`. If asleep, ask user asynchronously to open Linux; continue documentation/tests while waiting.
2. Run revised native UI check:
   `ssh -o ConnectTimeout=6 root@kindle.example.invalid '. /usr/local/bin/kindle-session-env; python3 -' < host/tests/check_instruments_ui.py`
3. Fix any geometry errors in the new Gtk.Overlay node buttons or clock. Test native clicked signals for all THREE buttons. On-device touch still needs user confirmation (previous test called a raw tap method and missed real touch behavior).
4. After test passes, stop ONLY the old panel PID after checking its cmdline; launch once with sourced `/usr/local/bin/kindle-session-env` and `nohup /usr/local/bin/deck-instruments </dev/null >/tmp/kindle-instruments.log 2>&1 &`. GTK app uniqueness otherwise reuses the old process instead of loading the new code.
5. Check log, sole process, GUI cache and native `clock_values()` timezone. Ask user to tap Kindle/Mac/Omarchy and confirm the new upper-right clock/look.
6. Finish `INSTRUMENTS.md` usage/rollback docs and update `PROGRESS.md` and `README.md` once final confirmation is known. Existing PROGRESS has an entry for the FIRST version; append the touch fix and final test count accurately.

## Device and safety details

- Kindle userspace Tailscale: **kindle.example.invalid**, root trusted SSH. Mac: mac.example.invalid (user `a.`); Omarchy: omarchy.example.invalid (zephyrillius). Kindle aliases already configured; do not dump all tailnet peers.
- GUI DISPLAY=:1, HOME=/home/alpine. Source `kindle-session-env` before GUI operations for the existing session bus and keyboard settings.
- Screen 1272×1696 portrait; 1696×1272 landscape. JWM tray height112. Native layout tests include work areas1584/1160 and reduced1076/779.
- Do NOT take Kindle GDK/framebuffer screenshots: that previously froze it. Tests use isolated GTK allocation checks; host pure Cairo previews are fine.
- Keep native GUI/power running; do NOT modify chroot mount/sleep/reader/jailbreak/DOOM. Current mount is /var/tmp/chroot/cyberdeck. Do not use old /var/tmp/alpine.
- Telemetry is once/minute only while panel active; paused or background panel does not initiate probes. Clock refreshes only a small region and only when the minute changes. No new always-on daemon/listener.
- Current GUI log: /tmp/kindle-instruments.log. Cache: /home/alpine/.cache/kindle-instruments/snapshot.json. Tool-launch errors: /tmp/kindle-instruments-actions.log.
- No subagents authorized. Continue independently. User dislikes unnecessary approval questions; work is authorized. Use required tool escalation for network/SSH only as the environment requires.
