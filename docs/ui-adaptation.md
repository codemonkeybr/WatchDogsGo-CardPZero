# UI adaptation: 640×360 → 320×170

**Status: proposal.** Based on the upstream screenshots (1280×720 = the
640×360 canvas at 2×) and a read of `watchdogs/app.py`. Nothing is
implemented here yet — see `ROADMAP.md` for what's since landed in
`czplatform/ui320.py` and `docs/screenshots/` for the result.

**Goal (owner):** stay as faithful to the original as possible; change only
what the smaller screen forces. The rule of thumb: **keep the look, re-budget
the layout** — text is never scaled, it just gets fewer columns and lines.

## The budget

| | Upstream (uConsole) | CardputerZero |
|---|---|---|
| Canvas | 640×360 = 230,400 px | 320×170 = 54,400 px (23.6 %) |
| UI font | Spleen 5×8, 9 px line pitch | same, at native size |
| Text capacity | ~126 cols × ~40 lines | ~62 cols × ~18 lines |
| Terminal pane | 110 px ≈ 12 lines × ~126 cols | must shrink (see below) |
| Physical text size | ~147 PPI effective (5″ 1280×720 shown at 2×, approx.) | ~190 PPI (1.9″, 320×170) → glyphs ≈ ⅕ smaller in real size |

The last row is the one real unknown: 5×8 glyphs should still be crisp (a
desktop render looked clean) but legibility on the actual 1.9″ panel needs an
on-device check before committing to the font size.

## Keep 1:1 (the identity)

- The 16-colour pyxel palette and the cyan-on-navy grid look.
- Spleen 5×8 at native size (the 8×8 font only where it still fits).
- HUD strip style, XP bar, badge chips, the tab bar with its highlighted
  selection row, `[x]` hotkey brackets.
- The per-tab hacker art + speech bubble, radar sweep widget, player marker,
  cluster bubbles, MeshCore toasts, colour-coded terminal output.
- Boot screen / logo, loot screen structure.

## What has to change (proposed)

1. **HUD top, 16 → ~10 px.** Always show: `LV:13 GHOST`, XP bar, battery.
   The seven badge chips (~175 px today) collapse to earned-only or a count;
   the zoom label moves into the map corner.
2. **HUD bottom, 16 → ~10 px.** Keep the counters (BLE / WiFi / HS / PWD /
   PWN) and GPS/LoRa state. Drop the `[TAB]Menu [`]Loot [S]Stop` hints —
   move them to a help overlay on `fn+H`, which is the CardputerZero's own
   convention for "show app help".
3. **Terminal: always-on pane → 3–4 line ticker + full-screen overlay.**
   The terminal is core to the "real tooling" feel, so it stays reachable on
   one key; it just stops owning 110 px permanently. Lines wrap/truncate at
   ~62 columns (most upstream log lines are ≤ 56 chars already).
4. **Map: 218 px → ~110–120 px strip.** Radar (~41 px circle today) can stay
   roughly as is; the small decorative radio sprite can go.
5. **Menu screen.** Upstream: list on the left, ~170×235 px hacker art on
   the right. Proposal: list ~220 px wide (≈44 cols; the item labels in the
   screenshots are ≤ ~25 chars) and the art at **exactly ½ scale**
   (171×256 → ~85×128 — an integer downscale keeps pixel art clean), speech
   bubble over its top. The five tab sprites need regenerating at the new
   size from the 848×1264 sources with the existing `convert_sprite.py` /
   `generate_hacker_sprite.py`, then a hand check.
6. **Sub-screens (the long tail, ~40 `_draw_*` methods).** MeshCore chat,
   MITM, Flipper, ESP32 flasher, captured data, network/portal pickers,
   whitelist, dialogs: each is a full-screen layout built off `W`/`H`. Review
   one by one; lists truncate at ~62 cols; the MeshCore chat moves from the
   8×8 font (40 cols) to Spleen (62 cols).
7. **Key hints** use the CardputerZero labels (arrows are `fn`+F/X/Z/C,
   Page Up/Down `fn`+L/M) — see the keyboard section of
   `docs/hardware-notes.md`.

## How to structure the code (decision for the owner)

- **A — display profiles (recommended).** Add a small `layout.py` with named
  rectangles computed per profile (`uconsole` / `cardputer`); `app.py`'s
  `W`, `H`, `HUD_*`, `TERM_*`, `MAP_H` read from it, and the draw functions
  that must differ branch on the profile. One codebase serves both devices,
  upstream merges stay cheap, and the result could be offered back upstream.
- **B — hard fork.** Rewrite the layout in place: fastest route to a 320×170
  look, but every future upstream merge collides in the same ~7.9k-line
  `app.py`.

Suggested split: profile constants for HUD / terminal / map; accept
per-profile draw code only for the menu screen and the sub-screens.

## Implementation status (2026-11-18)

**The code structure chosen differs from options A/B above:** neither a display
profile inside `app.py` nor a hard fork. `czplatform/profile.py` changes the
canvas globals of the vendored `watchdogs/app.py` at run time (`W, H`, the HUD /
terminal / map bands — module globals read at call time, imported by nothing
else) and `czplatform/ui320.py` replaces the draw methods that need a different
layout, only in the 320×170 profile. The vendored files stay byte-identical, so
upstream merges never conflict; the price is that new upstream HUD/menu items
won't appear in the compact layout until mirrored (re-check after each sync).

Done (screenshots in `docs/screenshots/320x170-*.png`, rendered from fake demo
data): top HUD, bottom HUD, the map/log split (below), the menu with its tabs,
scrolling list and per-tab character at half scale (85×128, generated by
`tools/make-sprites.py` from the original art with the original pipeline), and
the speech bubble. Text is the original Spleen 5×8 at 1:1. Measured on the CM0
at this canvas: ≈45–64 MiB RSS, 30 fps.

Still to do: the boot screen, every sub-screen (not yet toured), a `fn+H` help
overlay for the key hints removed from the bottom bar, an optional full-screen
terminal view, and the literals that still assume 640×360.

### Map and log are two views (owner's idea, 2026-11-18)

Keeping the original's always-on terminal under the map costs too much of a
170 px screen, so the two are separate and one key switches between them:

- **Map view** — the map gets everything between the two HUD bars (140 px). Its
  last line is a **ticker with the newest log entry** (colour-coded as in the
  log).
- **Log view** — a full-screen `> OUTPUT` panel: 15 lines, newest at the bottom,
  `L:<total>` and the running tool or `SCROLL +n` in the title. The map's radar
  and toasts are hidden meanwhile, and so are the game's CRT sweep lines (`_draw_scanlines`), which
  struck through the text on a 170 px screen — they stay on the map only (the menu
  too hides them).
- **Keys**: **ENTER** (OK) toggles map ↔ log, only while the map is the active
  screen (not in a menu, dialog, attack flow or sub-screen) — the original game
  doesn't use ENTER there. In the log view the arrows (`fn`+`F/X/Z/C`), PgUp/PgDn
  (`fn`+`L/M`, a page of 14 lines), Home/End (`fn`+`K/N`) scroll, **ESC** goes back
  to the map, **TAB** opens the menu. Those keys are consumed *before* the game
  sees them (an input filter on the keyboard injector), so they never pan the
  map or open the quit dialog. pyxel can't "un-press" a key in the same frame,
  which is why this is done at the evdev layer.

### Header and footer: what they show, what is open

| Bar | Shows (compact) | Decision / still open |
|---|---|---|
| Top | `LV:n TITLE`, XP bar + XP, hat, **earned** badges (only those that fit), zoom, battery | Kept — it is the game's identity. Open: a charging indicator next to `BAT` (the BQ27220 reports it); a clock (the device has an RTC; the original has none); badges collapse to a `★n` count if the bar gets crowded |
| Bottom | loot counters `BLE WiFi HS PWD PWN`, then right-aligned GPS (`GPS:OK`, `GPS:7sat`, `GPS:...`, `GPS:--`), LoRa (`LoRa:n`), and the active tools | The original's lat/lon (100 px) was dropped to fit. Open: show coordinates somewhere when there is a fix (e.g. in the log title or a map corner)? The `[TAB]Menu [`]Loot [S]Stop` hints moved out — a `fn+H` help overlay is still to do |
| Map's last line | the newest log entry, truncated to 62 columns | Open: scroll long lines as a marquee? |

## Workflow: this part needs no device

pyxel runs headless on a dev machine (`pyxel.init(headless=True)`, then
`pyxel.screen.save(path, scale)` — verified with 2.9.9 and 3.0.2, see
`tools/pyxel-smoke.py`). So each screen can be rendered to a PNG at 320×170
and reviewed next to the upstream screenshot. Plan: a small script that
drives the game into its canonical states (main, each menu tab, loot,
MeshCore, MITM) and dumps one PNG per state, so layout work is a tight
edit → render → compare loop with no hardware in the way.
