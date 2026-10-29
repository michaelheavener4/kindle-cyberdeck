# Kindle cyberdeck

Alpine Linux session for this jailbroken Kindle Paperwhite 6 (Sangria, firmware 5.20.1.0.2).

Amazon's kernel stays. It is the only kernel with drivers for this panel, the touchscreen, and Wi-Fi. There is no postmarketOS or mainline port for Bellatrix4, and flashing another Kindle's firmware would brick it. The Linux book stops the Amazon reader and store, then starts this chroot. Exit, or a reboot, brings the Kindle UI back. Doom, the jailbreak, and the OTA filler files are not modified.

The image is a loop-mounted ext3 file from [adiglase/alpine-kindle](https://github.com/adiglase/alpine-kindle) (GPL-3.0), built without Chromium. `launch/alpine.sh` is that project's launcher plus a bind of the userstore at `/mnt/kindle`.

## What the menu runs

The top level is grouped into **Personal**, **Games**, and **Dev**. Personal → Books opens the book assistant: describe a book, choose a numbered Soulseek result, and it downloads, adds a usable cover, converts to Kindle format, and copies the verified file to `documents/Books`. Its **On my Kindle** option lists existing books too. Exit Linux to read them in the normal Kindle Library.

On the Kindle, after Tailscale login:

- Terminal: a local shell
- Codex, Grok, OpenCode: `tmux` on this Omarchy machine, so a dropped Wi-Fi link resumes
- Omarchy shell: the same, in a `kindle` session
- MacBook: SSH to the existing `mac` host. The Mac does not trust the Kindle key yet
- Files: the Kindle userstore
- Pokemon Red, and any other Game Boy ROM: mGBA, with touch buttons. Put `pokemon-red.gb` in `/mnt/us/gb/`. Cartridge saves are `/mnt/us/gb/saves/<name>.sav`. QUIT writes the save. The ROM is not included.
- Chess: menu `c`. A large touch board. Play white, play black, or pass the Kindle between two people. The Kindle answers in about a second. The game is kept at `/mnt/us/chess/current.fen`. Lichess is a button on that screen. It uses the Kindle's Wi-Fi and a personal token with Board play, saved as `chess/lichess.token` (one line) or typed once. Time controls are 15+10, 10+5, and 30+0, casual unless you tap Rated. Bullet and blitz seeks are refused by Lichess for this kind of client, and the Kindle's own engine does not play those games. Not yet tried on the panel. No sound.
- Journal: menu `j`. Each day is plain text at `/mnt/us/journal/YYYY-MM-DD.txt`. The page works with the on-screen keyboard. It also tries a USB-C to USB-A keyboard. That host switch is not confirmed on this Paperwhite. Plug the adapter in after Linux is up. If no keyboard appears, the log is `linux/usb-host.log`.
- USB mouse: the same host switch. If a mouse enumerates, it moves the Alpine pointer and the cursor is drawn large for this panel. Touch still works. Leaving Linux puts the port back.
- Joy-Con: menu `y` pairs a left and a right Switch Joy-Con. Up and Down move the menu, A runs the line. In a Game Boy game the face buttons match the touch pad, Plus is Start, Minus is Select, and ZR is fast-forward. QUIT on the touch pad still writes the save. The Joy-Con book on the Kindle shelf turns reader pages: L or B back, R or A forward. Tap that book again to stop. A reboot stops it too. It does not install a boot service. The bridge is [kindle-hid-passthrough](https://github.com/zampierilucas/kindle-hid-passthrough) v3.19.0, kept on the userstore. Joy-Con (R) has been reported on a Paperwhite 5, not on this 5.20.1 panel. Nothing here has been tried on the glass yet. Pokemon stays silent.
- Omarchy screen: menu `d`. This laptop adds a headless screen, 1272×1696 at scale 4, to the right of its own display, so text is large on the 300 ppi panel. The Kindle pulls a grayscale picture about every 4 seconds and skips a repeat. Super+Shift+Alt+Right moves the current workspace onto it. Now, pause, and close sit on the bottom of the picture, which stays at 1:1. Close, or leaving Linux, removes the extra screen. Touch on the Kindle does not control the laptop. This needs the Tailscale login from item 7. It has not been tried on the panel. `~/.local/bin/kindle-display stop` removes a screen left behind.
- Sleep screen: one forecast picture, `screensavers/00-weather.png`. [kindle-custom-screensaver](https://github.com/chengandre/kindle-custom-screensaver) v0.5.0 draws it when the Kindle sleeps. Boot is unchanged, and a reboot restores Amazon's sleep screen. Tap the Custom Screensaver book once to turn it on, and again to turn it off. The picture stays as it was while the Kindle is asleep. Plug it in and run `~/.local/bin/kindle-weather` for a new one. The place is San Francisco. `kindle-weather --place "City"` changes it. This 5.20.1 firmware is newer than the 5.19.6 builds that project has confirmed. It has not been seen on this panel yet.

ChatGPT, MUSE, and Autopilot are not menu items. This machine has no ChatGPT client, and those two have no confirmed start command.

## Build

```sh
./build-rootless.sh
```

Outputs `release/alpine.ext3`, `release/swap.img`, and `release/alpine.sh`. Copy those to `/mnt/us` while Alpine is not mounted. Copy `launch/Linux.sh` and `launch/Linux-log.sh` to `documents/`, and `launch/run.sh` to `/mnt/us/linux/run.sh`. Eject, then tap Linux.

Do not plug in USB while `alpine.ext3` is mounted.

## Current menu additions

Personal contains **Chat**, **Books**, and **Archive.org**. Chat uses the Mac's Apple Foundation Models CLI by default, with local Ollama as an alternative, and saves conversations on Omarchy. The local hub starts on demand with `~/.local/bin/kindle-hub ensure`; NetSurf reaches it through an SSH tunnel. The Mac and Omarchy must be awake. Archive.org supports search, item details, public text reading, and scanned PDF pages.

Dev includes **MacBook shell**, **Mac FM AI**, and **Mac local AI**. Local AI offers 8B chat, an OpenCode coding agent, and a larger 14B coding chat using the already installed abliterated models. It refuses to load Ollama models while Cyberpunk runs. Mac-side helper source is `host/mac/kindle-local-ai.py`.

Settings includes **Display orientation** (portrait or either landscape direction), **Font size** (18, 22, 26, 30), and **Show / hide keyboard**. Font choice applies to the current menu terminal and future terminals; normal shell/application text retains its standard alignment, while Cyberdeck menu content is centered. Windows follow the docked keyboard's available space in either orientation.


Archive now uses stacked touch controls, a full-width search box and large buttons. Advanced search offers title, author, subject, collection, language, publication years, file format and availability. Sort by relevance, views, popularity, added date, publication date or title. Filters persist across result pages. Collection shortcuts, linked item metadata, reviews, file-format download lists, and reader page jumps provide more of Archive's native browsing options. Borrowing/account features and Wayback use the original site.


## Touch desktop and generative art

The current default is a touch dashboard, large browser controls, a full-width panel with six equally sized targets, and a docked on-screen keyboard. **Art Mode** has nine original code-driven styles, seeded rendering and a protected daily archive. See [ART.md](ART.md) for CLI commands and disabling it, and [TOUCH-UI.md](TOUCH-UI.md) for browser, desktop, transfer and rollback notes.

Archive's primary reading action is now **Send to Kindle & Read**, which opens supported documents in the native Kindle reader after a clean Linux exit. The native PDF handoff was verified on the device and confirmed by the user. The corrected runner keeps the native UI/power manager alive and uses `/var/tmp/chroot/cyberdeck` to avoid the old blank-screen exit loop.


## Native Lichess

**Games → Lichess · Online chess** opens the dedicated touch chess app signed in to your Lichess account. Pick 15+10, 10+5, or 30+0 to find a human opponent, or challenge a username. Games default to Casual; Rated is an explicit choice. The board adapts to portrait/landscape, faces your color, marks moves, and reconnects to the server. The local engine is disabled online. See [LICHESS.md](LICHESS.md) for sign-in, controls, verification, and rollback.
