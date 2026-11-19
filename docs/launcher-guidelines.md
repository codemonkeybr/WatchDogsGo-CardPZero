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
- `.desktop` keys it reads: `Name` (required), `Exec` (required), `Icon`
  (relative to `/usr/share/APPLaunch/` or absolute), `Terminal`, `Sysplause`,
  `Type` (must be `Application` if present), `Hidden` / `NoDisplay`.
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
- Icon size/style for the carousel (existing icons are named like
  `cli_100.png`, i.e. probably 100×100) — check one on the device.
- Whether `Exec=/usr/bin/sudo -n -- <wrapper>` passes the launcher's check (the
  first-party Cap apps use it, so very likely) — only needed if we end up
  needing root.
