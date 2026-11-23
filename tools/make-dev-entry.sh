#!/usr/bin/env bash
# Run ON the CardputerZero. Creates, in <project>/dev/, a wrapper script and a
# .desktop entry that start tools/cz-demo.py from the APPLaunch carousel, and
# prints the single sudo command that registers the entry with the launcher.
#
# Why a wrapper: the launcher validates Exec — shell metacharacters are
# rejected and a path must be an executable file — so Exec is a plain path to
# this script. The launcher rescans /usr/share/APPLaunch/applications about
# every 3 s, so no restart is needed after installing the entry.
# (M5's APPLaunch packaging guide, §2.)
#
#   bash tools/make-dev-entry.sh [project-dir]     (default ~/WatchDogsGo-CardPZero)
set -euo pipefail
ROOT="${1:-$HOME/WatchDogsGo-CardPZero}"
mkdir -p "$ROOT/dev"

cat >"$ROOT/dev/wdg-demo.sh" <<EOF
#!/bin/sh
cd "$ROOT"
exec "$ROOT/.venv/bin/python" "$ROOT/tools/cz-demo.py" --assets "$ROOT/assets" --seconds 300 --log "$ROOT/dev/cz-demo.log"
EOF
chmod 0755 "$ROOT/dev/wdg-demo.sh"

cat >"$ROOT/dev/wdg-demo.desktop" <<EOF
[Desktop Entry]
Name=WDG Demo
Exec=$ROOT/dev/wdg-demo.sh
Terminal=false
Icon=share/images/cli_100.png
Type=Application
EOF

# The game itself (czplatform runs the vendored WatchDogsGo). Bytecode caching is
# left on; the game logs to ~/.watchdogs/last_run.log.
cat >"$ROOT/dev/wdg-game.sh" <<EOF
#!/bin/sh
cd "$ROOT"
exec "$ROOT/.venv/bin/python" -m czplatform --canvas 320x170
EOF
chmod 0755 "$ROOT/dev/wdg-game.sh"

# Icon=<absolute path outside /usr/share/APPLaunch> looked supported from
# reading the launcher's source (launcher_platform.hpp's `path()` just
# forwards to an opaque IPC call, "Path", with no visible restriction) but
# did NOT work live (2026-11-20): the carousel showed every first-party app's
# fallback icon (an embedded M5Stack logo, home_icon_fallback.c) instead, with
# no error — LVGL's PNG decoder failing or the path not resolving both land
# on that same silent fallback. Every working app's Icon= is
# "share/images/<name>.png", resolved relative to /usr/share/APPLaunch/ —
# follow that convention instead of trusting the absolute-path reading.
cat >"$ROOT/dev/wdg-game.desktop" <<EOF
[Desktop Entry]
Name=WatchDogsGo (dev)
Exec=$ROOT/dev/wdg-game.sh
Terminal=false
Icon=share/images/watchdogs-icon-100.png
Type=Application
EOF

echo "created in $ROOT/dev/: wdg-demo.{sh,desktop} and wdg-game.{sh,desktop}"
echo
echo "Register the entries with APPLaunch (needs your sudo password, once):"
echo "  sudo cp $ROOT/assets/watchdogs-icon-100.png /usr/share/APPLaunch/share/images/watchdogs-icon-100.png"
for n in wdg-demo wdg-game; do
    echo "  sudo install -m 0644 $ROOT/dev/$n.desktop /usr/share/APPLaunch/applications/$n.desktop"
done
echo "Remove them later with:"
echo "  sudo rm /usr/share/APPLaunch/applications/wdg-demo.desktop /usr/share/APPLaunch/applications/wdg-game.desktop"
echo "  sudo rm /usr/share/APPLaunch/share/images/watchdogs-icon-100.png"
