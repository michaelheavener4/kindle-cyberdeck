# Progress

## Books and grouped menu (October 25)

- Installed top-level Personal / Games / Dev menus with keyboard/arrow navigation and Back. Books is Personal → b. `deck-books` opens the host `kindle-books` command in a persistent SSH/tmux session. Terminal connections now force UTF-8.
- Host app source is `host/kindle_books/`, entry point `host/kindle-books`, installed wrapper `~/.local/bin/kindle-books`. It uses the installed Nicotine+ protocol engine in a private, unshared profile, and existing Codex login for schema-constrained natural-language interpretation. Existing Nicotine config is unchanged.
- Searches always display a numbered result picker before downloading; format, size, and availability are shown. Identical filename/size copies are deduplicated and alternative formats are surfaced. No shell execution of peer metadata.
- Completed downloads are validated, converted to AZW3 as needed, and get a verified embedded cover. Covers come from existing metadata, matching Open Library art, or an original generated-art template with book-specific title/author typography. Original artwork is included in `host/kindle_books/assets/`.
- Delivery uses partial files and SHA-256 checks over root SSH. Calibre's Kindle driver identifies native thumbnail filenames; verified thumbnails go to `system/thumbnails` and `amazon-cover-bug`.
- On my Kindle / library reads actual device documents, including pre-existing books outside this bot. Opaque IDs are hidden in display titles and known jailbreak helper documents are omitted.
- Live test: Soulseek login and a 270-result search succeeded; Codex interpreted a natural-language request. Of Mice and Men downloaded, converted, and was delivered with cover and Library thumbnail. The actual Cyberdeck → Personal → Books path opened, listed on-device books, displayed real Soulseek choices, and a numbered selection completed download/delivery. The extra initial setup-test edition was archived outside documents.
- Eleven meaningful unit tests passed (explicit selection, first-result selection, live-library source, filename display, format ranking, duplicate peers, EPUB traversal, symlink rejection, wrong-author cover filtering, and blank/custom cover quality). Usage and dependencies are in `host/BOOKS.md`.

## SSH menu repair (October 25)

- Kindle successfully connected to Omarchy with an explicit IP, `/home/alpine/.ssh/id_ed25519`, and `tailscale --socket=/run/tailscale/tailscaled.sock nc` proxy.
- GUI runs as root with HOME=/home/alpine; OpenSSH looks up root's home from passwd, so the menu does not read Alpine's SSH config.
- Added `overlay/usr/local/bin/deck-fix-ssh` to install root's host aliases and absolute key path while preserving existing config. `launch/startgui.sh` invokes it for future builds.
- Shell syntax and effective SSH settings for both aliases checked locally.
- USB logs confirmed the dead Tailscale socket was misclassified as a running daemon. `deck-net` now checks JSON BackendState with a timeout and starts tailscaled under nohup with stdin detached. GUI startup restores the saved connection.
- Installed and read-back verified the updated networking, GUI startup, session cleanup, and SSH helpers over MTP. Originals are in `backups/2026-10-25-ssh-repair/`.
- Added signed Alpine armv7 Dropbear/utmps/skalibs packages plus this computer's public key under `linux/ssh-server/`. Verified signatures using the image's Alpine keys and loaded the ARM server under QEMU. Startup installs these offline and starts key-only Dropbear on loopback port 22, reachable through userspace Tailscale. It stops with the Linux session.
- The image's root home is uid 1000, so SSH server setup corrects ownership of root's home and SSH directory for key authentication.
- Live verification passed after unplugging USB and launching Linux: Tailscale restarted and rejoined its saved identity, key-only root SSH from Omarchy succeeded, and root's `ssh -G omarchy` used the correct user and Tailscale address.
- Kindle-to-Omarchy SSH with the plain `omarchy` alias succeeded as zephyrillius. tmux, codex, grok, and opencode were found in the remote login environment. Opened `/usr/local/bin/deck-connect omarchy kindle` under a PTY with HOME=/home/alpine and reached the interactive Omarchy tmux shell, matching menu option 5.

## Done

- Identified the device: Paperwhite 6, Sangria, Bellatrix4, firmware 5.20.1.0.2, kernel 5.15.41-lab126, armhf userspace, jb.sh v2.3.0.
- Alpine is a chroot. Amazon's kernel stays. Exit or reboot returns to the Kindle UI.
- The image is on the Kindle and the sizes matched. The desktop came up. The first launch died in `su` because the image's setuid helper is owned by uid 1000. The userstore `linux/startgui.sh` runs the session as root with `HOME=/home/alpine`. The menu works.
- A new ed25519 key is in the image and in this machine's `~/.ssh/authorized_keys`.

## In progress

- Tailscale menu item 7. It used to sit on the unchanged menu while `tailscaled` started with no output. The launcher now clears the screen, prints each step, and repeats the login URL. Launcher scripts are copied from `/mnt/us/linux/bin` at start, so the 1.5 GB image was not rebuilt.

## Not done

- Tailscale login has not been confirmed on the device. After the next Linux launch, item 7 should print a URL. The log is `linux/tailscale.log`.
- Mac authorized_keys. The SSH user on that host is the literal string `a.`
- ChatGPT, MUSE, and Autopilot commands.

## Mouse

- The Linux session tries the USB host switch once, then watches for a USB mouse and moves the Alpine pointer. Touch is not grabbed. The cursor theme is 64px so it can be seen on this panel.
- Closing the journal leaves the port in host mode. Leaving Linux restores it.
- Same unproven switch as the keyboard. Not tried on the panel.

## Journal

- Menu `j` opens field notes. Days are `/mnt/us/journal/YYYY-MM-DD.txt`.
- The page works with the on-screen keyboard. It tries to switch USB-C to host and types from a grabbed keyboard. That switch is not confirmed on this model.
- Not yet tried on the panel.

## Joy-Con

- Menu `y` pairs a Switch Joy-Con and can learn its button codes. The desktop uses the pad and A. mGBA uses the same buttons as the touch pad. The Joy-Con book taps the reader for page turns and does not install a boot service.
- The bridge is kindle-hid-passthrough v3.19.0 unpacked under `release/joycon/`. Its installer is replaced with a refusal. Not tried on the panel.

## Game Boy

- October 25 live investigation: the SDL mGBA process ran without an X window. Upstream SDL2 fallback requests an OpenGL window and accelerated renderer even after GL initialization fails. Added `host/kindle-sdl-software.c`, a scoped LD_PRELOAD shim that clears the OpenGL window flag, bypasses GL context creation, and selects SDL's software renderer. ARM build is `release/gb/libkindle-sdl-software.so` and is also in the overlay library directory.
- Local regression check reproduced failure with an SDL driver without OpenGL, then passed window creation, software renderer, streaming texture upload, and frame presentation with the shim. ARM binary compiled with clang/lld and warnings as errors; reproducible build is `host/build-gb-renderer.sh`.
- Save backed up on-device to `gb/backups/pokemon-red-before-controls-fix.sav` before tests.
- A GDK screenshot diagnostic caused a system-wide stall. Kernel threads, the screenshot process, and native power management entered uninterruptible I/O sleep; loop9 swap and loop1 root image were both backed by `/mnt/us` FSP/FUSE files. Display restart attempts did not recover it; user reset the Kindle. No further GDK screenshots will be used.
- Deployed and verified the renderer, touch pad, and launcher changes after reset. Disabled the unused active swap. Future image mounts use `/mnt/base-us`; file-backed swap is disabled by default.
- The default 8-bit visual also prevented SDL software textures from working. Launcher now automatically selects the 32-bit TrueColor visual, disables Super Game Boy borders, centers the undecorated 960x864 game, and places 1272x712 touch controls at y=872, above the tray. Menu is minimized during play and restored on exit. Controls map at full size initially to avoid a small ghost image.
- Live on-screen SAVE created a valid 9186-byte state file and mGBA reported State 1 saved. User confirmed the game is visible and A/Start controls work. No further display screenshots were taken. SRAM comparison showed only bank 0 scratch data changed during tests; banks 1–3 matched the pre-test backup.

- Menu `p` launches Pokemon Red from `/mnt/us/gb/pokemon-red.gb`. Menu `g` lists every `.gb` and `.gbc` in that folder.
- mGBA is installed from `linux/gb/mgba-apks.zip` the first time a ROM actually starts. Saves go to `/mnt/us/gb/saves/`. The ROM is not in the repo. It is on the Kindle at `/mnt/us/gb/pokemon-red.gb`.
- Not yet tried on the panel.

## Omarchy screen

- Menu `d` asks this laptop for a headless Hyprland output named kindle, 1272×1696, scale 4, to the right of eDP-1. The laptop script is `~/.local/bin/kindle-display`. Hyprland's config files are not edited.
- The Kindle pulls a grayscale picture about every 4 seconds and does not redraw when the picture matches the last one. Close removes the output. Leaving Linux tries to remove it too, before Tailscale is stopped.
- The picture path was checked on the laptop: create, mode, a 1272×1696 grayscale grab, and remove, with eDP-1 left as it was. The Kindle panel has not shown it. It uses the Tailscale SSH path, which is still unconfirmed.

## Chess

- Menu `c` opens a touch board. Play white, play black, or two players. The reply is a short search on the Kindle, about a second, with no extra packages.
- Move counts match the standard start position through depth 4 (197281), plus castling, en passant, promotion, stalemate, and a mate in one.
- The board is saved at `/mnt/us/chess/current.fen`. Not yet tried on the panel.
- Lichess is a button on the same screen. It talks to the Lichess board API over the Kindle's Wi-Fi. The token stays in `/mnt/us/chess/lichess.token` and is not kept in the program. Seeks are 15+10, 10+5, and 30+0 because that API rejects bullet and blitz. The on-device engine is not used for those games. A live login has not been tried on the panel.

## Sleep screen

- Custom Screensaver v0.5.0 is on the Kindle. The scriptlet is `documents/Custom Screensaver.sh`. The picture is `screensavers/00-weather.png`, and the package README is the only other file in that folder. The copied script, both binaries, and the picture matched local hashes. Doom, Linux, the jailbreak, filler, and `alpine.ext3` were not modified.
- The page is 1272×1696. It shows the San Francisco forecast from Open-Meteo: current temperature, high and low, the next four clock hours, and the next four days. `~/.local/bin/kindle-weather` redraws it while the Kindle is plugged in.
- Not yet seen on the panel. The upstream project has confirmed this screensaver through firmware 5.19.6, and this Paperwhite is on 5.20.1.

## Next check

Eject USB. Tap Custom Screensaver once, then press power. The sleep screen should show the forecast. Tap that book again to turn it off. A reboot also turns it off until the book is tapped again.

Then tap Linux and choose 7. The screen should say TAILSCALE immediately. Open the URL in a browser and approve the machine named kindle. After that login works, menu `d` is the Omarchy screen.

## 2026-10-25: Mac AI, web hub, keyboard and display

- MacBook shell now exports Homebrew/local PATH before attaching tmux and starts the Mac login shell. Interactive SSH reached the Mac prompt successfully.
- Onboard uses native docking and reserves its work area. Removed explicit startup coordinates that disabled docking; user confirmed the keyboard works. Session helpers reuse the existing D-Bus session.
- `kindle-window-fit` maximizes normal application windows, excluding Onboard and Game Boy controls, and refreshes existing maximized windows whenever the work area changes. Landscape verified at 1696×1272: keyboard y=779, height=381; terminal y=72, height=676, bottom=748. Keyboard hidden expands the terminal to height=1060. No Kindle screenshots or framebuffer capture were used.
- Settings offers portrait, landscape left/right, keyboard toggle, and saved terminal font presets 18/22/26/30. Rotation stays inside Xephyr; native Kindle stays portrait. Onboard is hidden/shown after rotation to refresh stale struts. Cyberdeck menus are centered and redraw on terminal resize; compact layouts omit the hint on short terminals.
- Dev adds Mac FM AI and Mac local AI. Mac `/usr/bin/fm available` reports available. Ollama already had Qwen3 abliterated 8B and Qwen2.5 coder abliterated 14B; created metadata-only kindle-chat/kindle-code/kindle-code-large aliases from existing weights. Isolated OpenCode config lives at `~/.local/share/kindle-ai/opencode.json` on the Mac. Cyberpunk guard blocks Ollama loading while the game runs. No weights downloaded and loaded-model list remained empty. FM generation and coding inference were deliberately not exercised during the game.
- Personal adds Chat and Archive.org via NetSurf and an SSH-forwarded, loopback-only host `kindle-hub` on port 8765. Chat stores conversation history locally and routes to Mac FM or Ollama; no paid API key. Archive supports search, details, public text pagination and public PDF scan rendering on the host. Actual search returned ten results and a public text item rendered successfully; Kindle fetched the chat page through its SSH tunnel.
- Sixteen tests pass (eleven existing books tests and five hub/Mac bridge tests). Hub tests cover escaped content, history-to-provider payload, reply persistence, Archive results/identifier validation, FM invocation and the no-inference gaming guard. Shell syntax checks passed. Helpers installed in the live Alpine image and persistent userstore linux/bin; JWM config updated. UI confirmation of chat replies/Archive pages on the physical Kindle remains for use; no live AI generation was triggered for testing.


- Archive UI now stacks search/type/sort controls, uses full-width fields and large tap targets, and adapts down to a 390px browser viewport. Advanced filters include title/creator/subject/description scope, title, author, subject, collection, language picker, year range, file format, and restricted-item exclusion. Added software, live music, datasets, collections and web media types; sorting and filters survive pagination. Default relevance uses the upstream default: the advanced API does not accept an explicit score sort.
- Collection shortcuts and collection items lead to local collection browsing. Item pages add linked metadata, reviews and public file format filtering. Text and PDF scan readers have page-jump forms. Original-site links cover borrowing/account features and Wayback.

## 2026-10-25/26: Touch desktop, art, e-ink images and native reading

- Added GTK Home dashboard, large touch navigation, window picker, files UI, settings and retained text-menu fallback. Global panel uses six equal-width components; its generator follows display rotation. Added browser GTK extension with tap-vs-swipe dispatch, original page-history callbacks, keyboard/tools controls and native-sized URL entry. Isolated GTK tests verified 150px scrolling without content press/release signals during the drag, a normal tap delivering its press/release, and Back firing main navigation rather than Find Back.
- Fixed Onboard's startup race: a Hide request no longer auto-activates the unconfigured D-Bus service. The real dock is 1272×508 in portrait, rather than 600×200. Settings backend is exported before the session bus starts. Browser window fitting is kept above the keyboard.
- Added original Python/Pillow one-bit artgen with nine modes, reproducible seeds, CLI parameters, protected per-date PNG/JSON archives, a below-app desktop layer, explicit gallery controls and a visible Menu exit. Daily rendering on the Kindle took about 1.1 seconds. Existing official daily art was not overwritten. See ART.md.
- Diagnosed and recovered an actual white-screen exit: the old runner left an already-mounted Alpine image mounted, then restarted framework, whose native pre-start script recursively chmods/chgrps /var/tmp except directories named chroot. Stopped that restart, moved the mount under /var/tmp/chroot/cyberdeck, restarted framework and the user confirmed Kindle Home returned. New runner keeps native UI/power management running and GUI teardown releases chroot-scoped helpers before unmount. Native services/rootfs configuration, jailbreak and DOOM binaries are not changed. User subsequently confirmed sleep while viewing art; fixed the gallery discoverability issue with a permanent Menu button.
- Archive reading preference changed to Send to Kindle & Read: preserve PDFs, convert supported book/doc formats on the host, checksum transfers, index the exact native document and hand off to KPP reader after clean Linux teardown. Legacy PDF routes remain only for old links. See TOUCH-UI.md for files and rollback.
- Final validation: 35 host tests pass. A 65,897-byte original PDF was copied to documents/Archive; SHA-256 matched on host and Kindle. Native scanner indexed it with a local PDOC key; deck-open-book then left Linux and opened the stock reader. User confirmed “it worked. i received the reader check.” The sample remains as Cyberdeck-Reader-Check.pdf. Native reader handoff is confirmed, beyond mocked tests.
- Global panel now uses six fixed equal hit areas generated from current screen width (211px each on the portrait display). Native JWM restart retained its PID and existing applications. Art gallery has a permanent Menu escape; the desktop art layer retains the HOME panel. Sleep was confirmed by the user while showing art. Reader-mode changes do not modify the original PDFs.


## 2026-10-25/26: Native Lichess account play

- Added Games → Lichess · Online chess (and text-menu entry), using the native GTK chess board rather than the website. Large rapid/classical seek controls, casual/rated choice, friend challenges, incoming challenge handling, server-position replay, reconnect/resume, color orientation, promotion, draw/resign/abort/claim controls. Local engine remains disabled online. Resign/Abort require confirmation; closing streams no longer blocks GTK while readline is active.
- Added official OAuth PKCE S256 sign-in through the private loopback hub, single-use expiring state and only board:play scope. Following explicit user approval, connected michaelheavener4 and sent the token over encrypted SSH stdin into private Alpine storage (0600). Direct account verification from the Kindle succeeded. The user confirmed the signed-in lobby and time buttons on the physical panel.
- Validation: 44 host tests pass; chess self-test passes. Native isolated GTK checks cover login/lobby/game/promotion in portrait, landscape and keyboard work areas, black orientation, touch selection and disconnected-move blocking. No live match or move was submitted during testing. Current game play remains user initiated. No desktop/power/jailbreak/reader/DOOM behavior changed. See LICHESS.md for file locations and backup reversal.

- Live follow-up: the user played an online game and won after the opponent resigned. A duplicate app instance introduced during updating caused competing event streams and a rate limit. Stopped the duplicate; added unique GTK application registration and reuse of existing windows. Repeated launches retained one PID. Added shared/persisted Retry-After cooldown, reconnect backoff, automatic account-bootstrap retry and a visible countdown. Final native logs confirmed account and event stream connections, and the user confirmed the lobby returned. Final suite: 44 tests pass.


## 2026-10-25/26: Archive form submission and per-file delivery fix

- Fixed the actual POST-handler failure behind “Choose an available public document”: its form accessor closed over `data`, which was reassigned to Archive metadata before reading the selected filename and action. Form values now remain in a separate variable. Regression tests exercise the real handler for both send-only and send-and-open, including Unicode/subdirectory filenames and colliding metadata keys.
- Added independent per-file Send to library / Send to Kindle & Read forms using hidden file and action fields. Ordinary source links are explicitly labeled Save original · browser download. Item pages show Kindle documents first, with All files and format filters retained. Legacy PDF/text preview routes also expose the native delivery actions.
- Validation: all 46 tests pass. Chrome submitted a real per-file Send to library action for Project Gutenberg’s Amusements in Mathematics through Archive; the job finished sent, producing an AZW3 with the existing cover pipeline and checksum-verified transfer. A read-only native content-catalog query confirmed it was indexed. The browser showed Saved in your Kindle library and Read on Kindle. No native reader handoff or Linux exit was triggered for this check. Test copy remains in documents/Books.


## 2026-10-26: Cyberdeck instrument panel

- Added native GTK/Cairo `deck-instruments` and stdlib-only, read-only `deck-instrument-probe`. Home and Dev have Instrument panel entries, with text-menu Dev → t. The panel draws a touchable monochrome schematic for Kindle, Omarchy and MacBook, then displays selected-machine load, memory, storage, uptime, battery when available, watched process counts, Ollama loaded models, FM command presence, persistent tmux sessions and host Archive/AI queue counts. Existing shell/agent/screen/AI helpers are launched only on explicit button taps.
- Remote probes use the existing trusted SSH aliases and pass the small Python probe over stdin; no remote agent or new listener is installed. Ollama is queried only through GET /api/ps. No inference, model loading, service starting or system configuration changes are done by telemetry. SSH checks are distinguished from offline machines, and cached values are clearly marked as last-good readings after a failed probe.
- Sampling is once per minute while the window is active; Pause holds the display and background windows do not initiate sampling. Only two bounded remote probes run at once. Closing terminates the collector's own subprocess groups. GTK application uniqueness reuses the existing panel instead of starting duplicate collectors.
- Tailscale requested a routine SSH check for Kindle → Omarchy; the user completed it. Read-only live probes subsequently reached all three machines. Mac Ollama was online with zero loaded models. Native GTK checks passed for all three node pages at portrait, landscape, and both keyboard-reduced sizes; node taps, shell action construction and Pause were verified with isolated fixtures. All 55 host tests pass.
- Helpers installed live and persistently in linux/bin. Reversible copies of previous menus are in /mnt/kindle/linux/backups/instruments-20261026-220908/. No JWM, native reader, sleep, jailbreak, DOOM or game-session configuration was changed.

- Update checkpoint before Omarchy restart: see RESUME-INSTRUMENTS.md. User reported the first custom diagram hit areas did not switch nodes and requested a stronger netrunner aesthetic plus upper-right time. Revision uses native GTK node buttons and adds a timezone-aware seven-segment clock, black machine band and framed meters. Revision is installed live/persistently but the existing panel process still needs a controlled relaunch after revised native UI checks. Latest host suite: 58 tests pass.
