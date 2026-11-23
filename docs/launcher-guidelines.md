# CardputerZero launcher / packaging guidelines — and how we follow them

Sources, read 2026-11-18 (all MIT-licensed, public):

- **AppBuilder** — <https://github.com/CardputerZero/AppBuilder>: README,
  `docs/QUICKSTART.md`, `docs/APP_BUILDER_JSON.md`, `scripts/pack-deb.sh`,
  `scripts/_template_desktop.in`, and the `examples/` (notably the Python
  `Demo_WifiScan` and the C `FrameBuffer_Game`).
- **Launcher** — <https://github.com/CardputerZero/launcher>: the official
  `docs/APPLaunch-App-打包指南.md` (APPLaunch packaging guide, in Chinese) and
  the source of `projects/APPLaunch/main/ui/{desktop_entry,launcher_app}.cpp`.

**Decision (owner's suggestion, adopted):** integrate and package the port the
way M5 prescribes instead of inventing our own scheme. We adopt their *launcher
and packaging* conventions; we do **not** adopt their LVGL/CMake template or
rewrite the UI — their own Python example renders the same way we do.

## How APPLaunch works

- It scans `/usr/share/APPLaunch/applications/*.desktop` and rescans about
  every **3 s**, so a new, edited or deleted entry shows up in the carousel
  without a restart (`systemctl --user restart APPLaunch.service` forces it).
- `.desktop` keys it reads: `Name` (required), `Exec` (required), `Icon`,
  `Terminal`, `Sysplause`, `Type` (must be `Application` if present),
  `Hidden` / `NoDisplay`.
- **`Icon` must be `share/images/<name>.png`, resolved relative to
  `/usr/share/APPLaunch/` — not an absolute path.** `launcher_platform::path()`
  (`include/launcher_platform.hpp`) just forwards the string to an opaque IPC
  call ("Path"), so an absolute path *looked* supported from reading the
  source alone — it wasn't, live (2026-11-20): the carousel entry still
  appeared but with every first-party app's **fallback icon** instead (an
  embedded M5Stack logo baked into the launcher binary,
  `ui/home_icon_fallback.c`) and no visible error (the fallback also covers a
  PNG the LVGL decoder can't read, so a decode failure and a path that didn't
  resolve look identical from the outside). Copying the icon into
  `/usr/share/APPLaunch/share/images/` and referencing it the same way every
  working app does fixed it immediately. `tools/make-dev-entry.sh` follows
  this now.
- **`Exec` is validated:** shell metacharacters are rejected; a path containing
  `/` must be an executable file; a bare command is only accepted from a small
  built-in whitelist (`bash`, `sh`, `python3`, `vim`, `vi`, `nano`…). So `Exec`
  is a plain path to a wrapper script — no arguments or `$HOME` expansion.
- **`Terminal=false` (default):** the launcher `fork`s and `execlp`s the
  program, **pauses its own screen refresh while it runs**, and returns to the
  carousel when it exits. Long-pressing **Home (fn+K) for 5 s sends `SIGINT`**;
  if the program is still alive 3 s later it gets `SIGKILL`. → the game must
  exit cleanly on `SIGINT`.
- **`Terminal=true`:** runs inside the launcher's built-in pty terminal.
  `Sysplause` (default true, only meaningful here) just controls the "Press any
  key to return…" prompt afterwards. It is **not** a pause-the-launcher flag
  (an earlier assumption of ours, now corrected).

This explains our early on-device test: drawing to `/dev/fb0` from an SSH shell
fought a launcher that wasn't paused and kept repainting its own frame; an app
started *by* the launcher gets the screen to itself.

## Lock screen, idle and backlight

From the launcher's own developer notes (`projects/APPLaunch/AGENTS.md`,
`ui_screensaver.cpp` in `CardputerZero/launcher`) and observed on the device:

- The launcher has a **lock screen** (legacy file names say "screensaver"). Per
  its source it paints a **full-screen black overlay** (so it looks black on
  every backend) and, *as a power optimisation on top*, also drives the
  backlight down (`launcher_media_controls::suspend_backlight`). It engages
  after **30 s of keyboard inactivity** by default (Settings → Screen →
  DarkTime; `0` disables auto-lock) and when **TAB is held for 3 s** on the
  home screen. Waking: any key shows a wallpaper, TAB arms, ENTER unlocks.
- **OPEN (left open by the owner): does the lock only paint black, or does it
  really switch the backlight off on this unit?** The owner can't tell by eye.
  The sysfs `brightness` isn't conclusive — it read 100/100 while the screen was
  black (20:21) and 0 in an earlier probe. A way to settle it later: compare the
  BQ27220 `current_now` (`/sys/class/power_supply/bq27220-0`) awake vs locked.
  A first sampling (20:26–20:27) was **inconclusive**: sysfs `brightness` read 0
  in both samples and the battery current was ~598 mA in both — but the device
  was *charging*, which masks the display's share of the load.
- **It is switched off while an external app runs:** the launcher calls
  `ui_screensaver_set_foreground(0)` before handing input/timers to the app and
  `ui_screensaver_set_foreground(1)` when it comes back, which *clears* the lock
  and restarts the idle interval. So a `Terminal=false` app of ours is never
  auto-locked — good for a map you watch without touching keys, costly for
  battery. Screen policy during long wardriving sessions is up to us
  (ROADMAP 1.8). **Verified by the owner (2026-11-18):** with the demo left
  open the screen never locked; it locked only after the app was closed.
- **Backlight from the app side:** `/sys/class/backlight/backlight/brightness`
  (0–100) is `root:video rw-rw-r--`, so a non-root app in group `video` can
  dim/blank it. (The launcher's own `cp0_backlight_*` calls are a C ABI for its
  LVGL apps — the `cp0_lvgl` component — and aren't reachable from Python.)
- Practical consequence for development: after an app exits, the launcher
  restarts its idle timer and locks 30 s later; a framebuffer read
  (`tools/fb-screenshot.py`) of a locked screen returns a single colour.

## Two ways to add an app

1. **A `.desktop` file only** (their "quick deploy", for development): drop a
   `.desktop` into `/usr/share/APPLaunch/applications/` (needs `sudo install`)
   with `Exec` pointing at any executable, e.g. in the home directory. No
   `.deb` needed. `tools/make-dev-entry.sh` generates a wrapper + entry for our
   demo and prints the one `sudo install` line.
2. **A `.deb`** (distribution): installs under `/usr/share/APPLaunch/` —
   `applications/<pkg>.desktop`, `bin/` (executables), `lib/`, `share/images`
   (icon, referenced as `Icon=share/images/<name>.png`), `share/font` — with
   `Section: APPLaunch`, `Architecture: arm64`, name
   `<pkg>_<version>-<revision>_arm64.deb`. AppBuilder's `scripts/pack-deb.sh`
   builds it from a per-app `packaging/` folder: `meta.env` (`PKG_NAME`,
   `PKG_VERSION`, `PKG_DEPENDS` = apt packages, `APP_NAME`, `APP_EXEC`,
   `APP_TERMINAL`, `APP_ICON`), `stage.sh`, optional `build.sh`, `postinst`,
   `icon.png`. Install with `scp` + `sudo dpkg -i`.

## What the official examples show

- **`Demo_WifiScan` (Python):** Pillow draws a 320×170 image, converts it to
  RGB565 and writes it into an **`mmap` of `/dev/fb0`**; keys come from
  `/dev/input/event*` (the TCA8418 keyboard); ESC/q quits. Dependencies are apt
  packages (`python3-pil`, `python3-numpy`, `iw`). Its wrapper runs
  `sudo -E python3 …`, and its `postinst` adds the user `pi` to the `video` and
  `input` groups — the same non-root route we measured (our user is already in
  both groups).
- **`FrameBuffer_Game` (C):** the same pattern with `mmap` + evdev, 16 or 32 bpp.
- This is exactly the architecture we prototyped: headless pyxel → RGB565 →
  `mmap` of `/dev/fb0`, keyboard from evdev (`tools/cz-demo.py`).

## What we adopt, and what we don't

| Adopt | Don't (for now) |
|---|---|
| `.desktop` + `.deb` layout under `/usr/share/APPLaunch/`, `Terminal=false` | LVGL/CMake `Template` and `czdev new` — the game stays Python/pyxel |
| AppBuilder's `packaging/` convention (`meta.env`, `stage.sh`, `postinst`, icon) and `scripts/pack-deb.sh` | A per-app **systemd service** (the AppBuilder README mentions one, but installed apps don't use it and the launcher itself starts apps) |
| `fb0` `mmap` + evdev at runtime; exit cleanly on `SIGINT` | Publishing to the AppStore (`czdev publish`) — owner wants community feedback first |
| apt `Depends:` for system libraries | Running as root by default: prefer non-root (groups `video`/`input`/`gpio`/`spi`/`i2c` already cover the device nodes); use the `sudo -n --` + sudoers pattern only for what really needs it |
| An `app-builder.json` (with a 320×170 screenshot) kept in the repo so a later store listing is possible | |

## Still open

- **pyxel is not in Debian.** Bundle its aarch64 wheel contents inside the
  package (e.g. under `/usr/share/APPLaunch/apps/<pkg>/vendor`) rather than
  relying on `pip` at install time.
- The AppBuilder `postinst` hard-codes the user `pi`; ours must handle the real
  login user (here the user is already in `video` and `input`).
- ~~Icon size/style for the carousel~~ confirmed: 100×100 PNG, 8-bit RGBA,
  color type 6, non-interlaced (`watchdogs-icon-100.png`, rendered from the
  vendored `assets/watchdogs-icon.svg` with `cairosvg`).
- Whether `Exec=/usr/bin/sudo -n -- <wrapper>` passes the launcher's check (the
  first-party Cap apps use it, so very likely) — only needed if we end up
  needing root.
