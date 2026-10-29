# Kindle touch UI

The default launcher is a GTK dashboard with Personal, Games, Dev and Settings, large two-column tiles, touch-scroll lists, a file browser, terminal font presets and Art Mode. The original `cyberdeck` text menu remains available in Settings.

The global desktop panel has six equal-width targets: HOME, APPS, KEYS, UP, DOWN, CLOSE. APPS chooses among open windows; UP/DOWN scroll the current application (terminal scrollback when using XTerm). Panel sizing is recalculated after rotation. Title-bar and menu targets are enlarged.

## Browser

`kindle-browser` keeps the existing NetSurf engine and loads a small GTK extension, `libkindle-touch-browser.so`. Its large toolbar provides Back, Forward, Home, Keys and Tools. Tools provides page scrolling, text size, reload and a selection-mode toggle. Swipe mode defers clicks until release, converts drags into scrolling and prevents accidental highlighting. URL-bar editing remains normal. History buttons track the real main navigation toolbar rather than the Find toolbar.

The extension is loaded only into the browser and clears its preload setting before image-loader subprocesses launch. Build it with `sh host/build-touch-browser.sh`. The default keyboard is the configured full-width Onboard dock; hiding it never auto-launches the small D-Bus default. Future D-Bus sessions inherit the correct settings backend. Window fitting follows the keyboard and handles browser geometry changes.


## Archive → native Kindle reader

Archive search and item pages remain in the touch browser. For books, PDFs, magazines and supported documents, select **Send to Kindle & Read**. The host downloads a public file, converts EPUB/text/DOCX when needed, verifies its Kindle copy and asks the scanner to index it. The native reader helper locates the exact document in the content catalog, leaves Linux cleanly and opens it using the KPP reader's document key. **Send to library only** leaves Linux open. PDFs retain their original layout and quality and go into `documents/Archive`; converted books use `documents/Books`.

The previous web PDF reader routes remain for existing links, but are no longer the main item-page reading action. Borrowing/restricted files still use Archive's original access flow; the transfer helper does not bypass restrictions. Downloads are limited to 250 MB per document.

Host service: `~/.local/bin/kindle-hub ensure`, bound to localhost port 8765 and accessed through SSH. Data and cached originals are under `~/.local/share/kindle-hub`. Transfers are recorded in its SQLite database. Kindle helpers: `deck-open-book` and `linux/reader-handoff.sh`; diagnostics are `linux/reader-open.log`.

## Exit and sleep

Linux runs from `/var/tmp/chroot/cyberdeck`, underneath a directory Kindle's startup scripts explicitly exclude from recursive permission repair. It uses native backing storage, without file-backed swap. The runner leaves Kindle's native GUI and power manager alive. GUI sessions clean up their own chroot even when the image was already mounted. Surviving chroot processes are terminated before bind mounts and loop devices are released. No native Upstart configuration is edited.

Home → Kindle offers Return to reader or Sleep Kindle. The native power button continues to control sleep/frontlight normally. On the first old-style recovery, the native framework was stopped, the live mount moved into the excluded directory and the reader restarted successfully without a reset.

To reverse visual changes, use the saved JWM/launcher backups, or disable only art with `artgen disable`. Preserve the corrected mount/runner behavior to avoid restoring the old exit failure.


### Archive file actions

Reload existing Archive pages after the form fix. Each supported public file now has **Send to library** and **Send to Kindle & Read** buttons. These submit the exact filename and intended action independently of the ordinary browser download link. Item pages default to **Kindle documents**; select **All files** for source images, archives and metadata. **Save original · browser download** intentionally opens the browser’s regular save dialog. Existing text/PDF preview pages also include native delivery buttons.

The real per-file transfer flow was verified with *Amusements in Mathematics*: conversion, cover handling, checksummed transfer, native library catalog registration, and the final Read on Kindle button. The small test copy remains in the library.
