# Generative art

`artgen` makes original procedural, black-and-white PNGs entirely on the Kindle. The default `lsystem_flower` is recommended: sparse recursive botanical growth, clean strokes and plenty of white space. It has no downloaded artwork, animation, model inference, or continuous refresh.

## Touch use

Home → Art Mode opens the gallery. The always-visible **Menu** button returns to Home. Tap the composition to reveal **New piece**, **Next style**, **Today**, and **Back**. The passive desktop layer sits below application windows; closing the last application reveals it. The desktop panel remains available. The gallery is explicitly full-screen.

The native Kindle UI remains running underneath Linux. Power/sleep is handled by Kindle, not by a simulated brightness overlay. The art layer does not inhibit suspend. Generation occurs on request and when an awake desktop notices a new local date (checked hourly, without periodic painting). Missed days during power-off are not generated retrospectively.

## Commands

```sh
artgen list-modes
artgen generate --mode lsystem_flower --seed 1234
artgen generate --mode geometric_grid --seed 1234 --density .7 --stroke 3
artgen generate --mode conceptual_text --text 'LEAVE ROOM / FOR QUIET'
artgen generate --mode topology_map --symmetry 2 --invert
artgen generate-daily
artgen show-latest
artgen set-background --latest
artgen cycle
artgen disable
```

Re-enable with `artgen set-background --latest`. For a chosen variant, use `artgen set-background --path /mnt/kindle/art/variations/NAME.png`. Set `--width` and `--height` together to override display detection. CLI generation takes density .2–2, stroke .5–12, complexity 1–8, spacing .4–3, symmetry 1–8 (bilateral mirroring when greater than one), inversion and text. Some parameters naturally matter more to particular styles.

Modes: `lsystem_flower`, `branching_tree`, `geometric_grid`, `line_field`, `ink_gesture`, `ascii_poem`, `conceptual_text`, `topology_map`, `rule_drawing`. All are original rule systems, not copies of a particular artist's compositions.

## Daily archive and files

- Renderer: `/usr/local/bin/artgen`; persistent copy: `/mnt/us/linux/bin/artgen`.
- Daily pieces: `/mnt/us/art/daily/YYYY-MM-DD.png` plus `.json` parameters/seed metadata.
- Variations: `/mnt/us/art/variations/`.
- Desktop image: `/mnt/us/art/current.png` and `current.json`.
- Configuration: `/mnt/us/art/config.json`; `timezone` is currently `America/Los_Angeles`.
- Disable flag: `/mnt/us/art/disabled`.
- Display diagnostics: `/mnt/us/art/display.log`.

Inside Alpine, `/mnt/us` above is exposed as `/mnt/kindle`. `artgen --archive /some/folder ...` uses another archive, useful for experiments and tests.

Exactly one official PNG is reserved per date under a file lock. Running daily generation again preserves that day's PNG and metadata, even if settings or code changed. Its deterministic seed is derived from `cyberdeck-art-v1:YYYY-MM-DD`. Only an explicit `artgen generate-daily --force` overwrites an official piece. Ordinary **New piece** does not replace it.

PNG writes are atomic; display failures retain the previous image. One-bit images do not depend on grayscale. Desktop scaling uses nearest-neighbor filtering and no screenshot/framebuffer capture.

## Dependencies and reversibility

Python 3 and Pillow generate images. GTK3, PyGObject and pycairo display them, using the same lightweight libraries already used by the desktop. `tzdata` supplies the configured local date. No daemon is installed in Kindle's boot services; the art process belongs to the Linux session.

`artgen disable` removes the art layer and prevents its next-session startup. It leaves all archived art intact. The GUI Settings screen has the same enable/disable actions. The jailbreak, DOOM and native reader binaries are not modified.

Before the touchscreen overhaul, launchers and JWM settings were backed up under `/mnt/us/linux/backups/touch-overhaul/`. Keep the safer mount location `/var/tmp/chroot/cyberdeck` and the native-friendly runner even when changing the visual UI; the old runner could leave Kindle's reader blank on exit.
