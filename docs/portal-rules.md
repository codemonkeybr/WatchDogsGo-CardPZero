# WDGWars portal — rules for forks and tools

Source: the upstream README, section **"Rules for forks and tools that use the
portal"** —
<https://github.com/LOCOSP/WatchDogsGo#rules-for-forks-and-tools-that-use-the-portal>
(read 2026-11-18 from upstream `main`). That section did **not** exist in the
local checkout we planned to vendor from (v0.9.x), and the maintainer may edit
it — re-read it before touching `plugins/wardrive_upload.py` or any other code
that talks to `wdgwars.pl`, and keep this page in sync.

## The rules (paraphrased)

1. **Introduce yourself.** Keep the User-Agent start
   `WatchDogsGo/<version> (<platform>-<hwid>; Python/<x.y>)` and append your
   own tag after the bracket, e.g. `… Fork/MyFork-2.0`. The fork still counts
   in the ranking and bug reports stay traceable.
2. **Don't impersonate hardware.** `uConsole-…` only on a real uConsole; on
   anything else report the truth (`RPi-…`, `Linux-…`).
3. **A separate tool isn't WatchDogsGo.** Bridges, converters and scripts that
   send data use their own product name at the start of the User-Agent.
4. **Respect the limits.** `/api/rabbits` about once a minute,
   `/api/game-state` every 30–60 s, uploads after a session or in batches;
   on HTTP 429 wait as long as `Retry-After` says.
5. **The player's key stays with the player.** Prefer code pairing
   (`/api/device-pair`) over pasting the 64-char key; never send the key
   anywhere except `wdgwars.pl`.
6. **Only what the server accepts counts.** Self-declared counters (own XP,
   etc.) aren't ranked, and the same session must not be uploaded twice.
7. **No WiFi-cracking material.** The portal doesn't accept PMKID or
   handshakes — don't add uploading of that data. (The in-game WPA-SEC upload
   goes to a different, third-party service and is unaffected.)
8. **Read data by header, not by column number.** Parse WiGLE files by header
   names (1.6 adds a column); an SSID containing a comma must be quoted.

## What this means for the CardputerZero port

- **User-Agent:** `WatchDogsGo/<ver> (<platform>-<hwid>; Python/<x.y>)
  Fork/CardputerZero-<ver>`. Our fork is still "the game", so it keeps the
  `WatchDogsGo/` token and adds the `Fork/` tag (rule 1). Any separate helper
  we ship that talks to the portal gets its own product name (rule 3).
- **Platform string:** never `uConsole-…`. The device-tree model here is
  "Raspberry Pi Compute Module 0 Rev 1.0", so upstream's new platform
  detection (commit `a3e8e54`) should land in the `RPi-…` bucket — verify
  after vendoring, and don't fake it. If a dedicated `CardputerZero-…` platform
  value is wanted, ask the maintainer rather than inventing one.
- **Pairing UX (rule 5):** typing a 64-char key on a 46-key handheld is
  painful, so `/api/device-pair` is more than a courtesy here. Upstream's
  README says pairing exists in the API layer "once a UI exposes it" — giving
  it a proper screen is a real task for this port (ROADMAP 4.5).
- **Rate limits and 429 (rule 4):** check that the vendored plugin honours
  `Retry-After`; on a battery-powered handheld it also saves power.
- **Internal-radio bridge (rule 8):** if `wdg_wifi_bridge.py` writes WiGLE CSV
  (`format_network_csv`), make sure SSIDs with commas are quoted.
- **No handshake/PMKID upload to the portal (rule 7):** nothing in the port
  should add that.

## Upstream drift to account for when vendoring

Our planned base was `7427fbf`. Upstream `main` is now at `8a2cb54` (v0.10.0+),
four commits later:

| Commit | Subject |
|---|---|
| `8a2cb54` | fix(portal): detect uConsole via the clockworkpi-uconsole boot overlay |
| `8f1d91d` | feat(portal): show WDGWars White Rabbit targets + game-state on the map |
| `a3e8e54` | feat(portal): detect uConsole vs RPi vs Linux in the UA platform field + fork rules in README |
| `72441cb` | chore: bump version to 0.10.0 |

The `feat/aiov2-wifi-bt-fallback` branch (4 commits, internal-radio bridge
fallback) sits on `7427fbf`, so it needs rebasing onto upstream `main` before
we vendor from it (ROADMAP 1.1).
