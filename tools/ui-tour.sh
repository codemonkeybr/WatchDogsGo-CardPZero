#!/usr/bin/env bash
# Render the game's screens to PNGs with no hardware (dev machine) — the loop
# for ROADMAP 1.2 (re-laying the UI out for 320x170).
#
#   tools/ui-tour.sh [outdir] [canvas]      defaults: ./ui-tour  320x170
#
# Runs the real game headless through czplatform with the demo loot DB
# (tests/fixtures/demo-data: Lv.13 GHOST, badges, counters), a fake 82 % battery
# and a scripted keyboard tour: boot screen, main map, then each menu tab.
# Each PNG is the panel view (320x170, upscaled 3x for reading).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "${1:-ui-tour}"
OUT="$(cd "${1:-ui-tour}" && pwd)"
CANVAS="${2:-320x170}"

STEPS="wait:40,png:$OUT/01-boot.png,key:RETURN,wait:90"
# fill the game's log, so the ticker shows the newest line and the log view is full
for i in $(seq 1 22); do
    STEPS+=",log:[LoRa] node $i heard rssi -$((50 + i))"
done
STEPS+=",log:[WARN] GPS not found,wait:3,png:$OUT/02-main.png"
# ENTER on the map switches to the full-screen log (320x170 profile) and back
STEPS+=",key:RETURN,wait:12,png:$OUT/03-log.png,key:RETURN,wait:12"
STEPS+=",key:TAB,wait:15,png:$OUT/04-menu-scan.png"
n=5
for tab in sniff attack addons system plugin; do
    STEPS+=",key:RIGHT,wait:10,png:$OUT/0$n-menu-$tab.png"
    n=$((n + 1))
done
# the loot database (backtick), both pages
STEPS+=",key:ESCAPE,wait:10,key:BACKQUOTE,wait:10,png:$OUT/10-loot-1.png,key:RIGHT,wait:8,png:$OUT/11-loot-2.png"
STEPS+=",quit"

cd "$ROOT"
CZ_FAKE_BATTERY="${CZ_FAKE_BATTERY:-82}" env -u DISPLAY PYTHONDONTWRITEBYTECODE=1 \
    .venv/bin/python -m czplatform --dry-run --seed tests/fixtures/demo-data \
    --canvas "$CANVAS" --script "$STEPS" --stats-every 100000 2>&1 \
    | grep -E "Traceback|Error|error|script finished" || true
ls "$OUT"/*.png
