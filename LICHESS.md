# Native Lichess on the Kindle

Open **Games → Lichess · Online chess**. The text-menu equivalent is
**Games → Lichess online**; the command is `deck-chess --lichess`.

This is the native GTK chess board, not the Lichess website. Once connected,
the Kindle talks directly to Lichess over HTTPS; the computer and Mac do not
need to stay awake for a game.

- Tap **15+10**, **10+5**, or **30+0** to find a human opponent. The numbers
  mean starting minutes and added seconds per move. **15+10** is a good
  default for the e-ink panel.
- Games start **Casual**. Tap **Casual** to switch to **Rated** before seeking.
- To play someone specific, enter their username and tap **Challenge**.
  A fresh session uses 15+10; otherwise it uses the last selected time.
- Incoming standard-chess challenges have **Accept** and **Decline** buttons.
- Tap a piece, then its destination. Legal destinations are marked; promotion
  offers Queen, Rook, Bishop, and Knight. The board faces your playing color.
- Draw, resignation, early abort, and eligible disconnect-win claims are
  available during games. Resign and Abort require a second tap.
- The board redraws for moves and selection, with no animation. Clocks update
  less often when plenty of time remains, then more frequently near time trouble.
- A dropped game stream reconnects and replays the server's position. Move
  entry waits for that state. **Reconnect** also checks for a game to resume.
- **Leave game** requires two taps and does not resign. The clock continues;
  reopening Lichess resumes an available standard game. Closing Linux or
  pressing power does not pause an online game.

Lichess's Board API supports public seeks in rapid/classical time controls.
The local engine, Undo, and local game controls are disabled online.
See the [official Board API](https://lichess.org/api#tag/Board).

## Connecting an account

On Omarchy, run `~/.local/bin/kindle-hub ensure`, then open
<http://127.0.0.1:8765/lichess> in a desktop browser. Click **Sign in with
Lichess**, review the account, and approve **Play games using the Board API**.
The native app's **Account** button opens the same connection page via the
existing private browser tunnel; desktop sign-in is easier on the Kindle.

OAuth uses PKCE S256, random single-use state, a 15-minute authorization
window, and only the `board:play` scope. The access token is stored with mode
0600 on this computer and transferred to the trusted Kindle over SSH stdin.
It is not placed in command arguments or logs. If Linux is asleep, the login
remains saved on the computer; wake Linux and click **Send login to Kindle**.
An open Kindle login screen checks for its arrival every three seconds.

Token files (private; do not share):

- Omarchy: `~/.local/share/kindle-hub/lichess-account.json`
- Kindle Alpine: `/home/alpine/.config/kindle-chess/lichess.token`

The old `/mnt/kindle/chess/lichess.token` is accepted for migration. A personal
Board-play token can also be entered in the masked native login field.
To revoke access, use [Lichess's token settings](https://lichess.org/account/oauth/token).

## Files, verification, and reversal

- App: `overlay/usr/local/bin/deck-chess`
- Menus: `deck-home-ui`, `cyberdeck`; browser route helper: `deck-web`
- Login bridge: `host/kindle_lichess.py`; routes in `host/kindle-hub`
- Live Kindle helpers: `/usr/local/bin/`, persisted in `/mnt/kindle/linux/bin/`
- Local game saves remain `/mnt/kindle/chess/current.fen`; online positions
  are reconstructed from Lichess and do not replace the local save.

No new runtime packages were needed: Python stdlib, GTK3/Pango/Cairo, the
existing chess font, and the existing host hub provide everything.

Validation: 44 host tests, the chess legality/self-test, and an on-Kindle
isolated GTK harness covering login/lobby/game/promotion in portrait,
landscape, and reduced keyboard work areas. Castling, en passant and all
promotion choices are exercised. Real account authentication succeeded from
the Kindle, and the user confirmed the signed-in lobby on the panel. No real
game was created or move submitted for testing; that remains user initiated.

To remove the menu change, restore the four backed-up helper files from
`/mnt/kindle/linux/backups/lichess-20261026-042941/` to their corresponding live
and persistent locations, then close/reopen Home. Files prefixed
`_usr_local_bin_` belong in `/usr/local/bin/`; files prefixed
`_mnt_kindle_linux_bin_` belong in `/mnt/kindle/linux/bin/`.
No JWM, sleep, jailbreak, native reader, or DOOM settings were changed.


## Live-game follow-up

The user played a real online game and reported a win by opponent resignation; the Lichess profile also showed the win. Two app instances during the update had repeatedly displaced the account event stream and triggered throttling. The duplicate was stopped, and the app now uses a unique GTK application identity plus compatibility handling that focuses an existing board rather than launching another. Repeated launches were tested on-device and retained the same sole chess PID.

Reconnects now back off after repeated failures. HTTP 429 honors Retry-After with at least a 60-second cooldown; the deadline is shared across clients and persisted across app restarts. Account sign-in retries automatically after the cooldown instead of leaving the lobby stuck, and the label shows the remaining wait. The final Kindle log confirmed account authentication and an open event stream; the user confirmed the lobby returned.
