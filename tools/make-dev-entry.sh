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

echo "created $ROOT/dev/wdg-demo.sh and $ROOT/dev/wdg-demo.desktop"
echo
echo "Register the entry with APPLaunch (needs your sudo password, once):"
echo "  sudo install -m 0644 $ROOT/dev/wdg-demo.desktop /usr/share/APPLaunch/applications/wdg-demo.desktop"
echo "Remove it later with:"
echo "  sudo rm /usr/share/APPLaunch/applications/wdg-demo.desktop"
