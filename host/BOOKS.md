# Cyberdeck Books

Open **Personal → Books** on the Kindle. The terminal app runs on Omarchy over SSH in a `books` tmux session.

1. Describe a book, or select **Find a book**.
2. Review numbered Soulseek matches, including format, size and availability.
3. Select a result number. A search alone never starts a download.
4. Completed downloads are converted where necessary, get an embedded cover and Kindle Library thumbnail, and are copied with a SHA-256 check.
5. Exit Linux to read the book in Kindle Library.

**On my Kindle** / `library` reads the device's documents directory, including books not downloaded by this assistant. Known jailbreak helper documents are omitted. `status` shows download/delivery jobs. Pending jobs resume when Books reopens; a detached tmux session keeps running.

## Dependencies and accounts

- Omarchy: system Python with installed Nicotine+ (`pynicotine`), Pillow, Calibre (`ebook-convert`, `ebook-meta`, `calibre-debug`), Fontconfig, SSH, and the logged-in Codex CLI.
- Existing Soulseek credentials are read from `~/.config/nicotine/config`; that file is not changed. The assistant uses a separate private Nicotine profile with no shared folders and no after-download commands or plugins.
- Natural-language interpretation uses read-only, ephemeral Codex runs with JSON-schema output. Plain `search TITLE AUTHOR`, library and status do not need the AI parser.
- State, downloads, covers and jobs are under `~/.local/share/kindle-books` (directory mode 0700). One Soulseek session per assistant is protected by a lock.
- `~/.local/bin/kindle-books` launches the source in this project. The Kindle helper is `deck-books`.

## Covers

Keep a usable embedded cover first. Otherwise query matching title/author metadata at Open Library, then fetch its cover. If no suitable cover is available, compose a new 1200×1800 cover from original generated artwork with the book's title and author. Artwork is included under `kindle_books/assets`; fallback generation requires no runtime image API credentials. Cover provenance is saved beside each cached cover.

Calibre verifies that a usable cover survives in the final file. Its Kindle device driver supplies the correct thumbnail filename from the book's embedded identifier. The assistant writes the thumbnail to both `system/thumbnails` and Calibre's `amazon-cover-bug` recovery cache.

## Validation

```sh
python3 -m unittest discover -s host/tests -v
kindle-books --intent 'Find Pride and Prejudice by Jane Austen'
kindle-books --search 'Mice Men Steinbeck' --seconds 18
kindle-books --library
```

Search diagnostics do not download. `--send PATH --title TITLE --author AUTHOR` runs conversion, cover and verified Kindle delivery for a local book.
