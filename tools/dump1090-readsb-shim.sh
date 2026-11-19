#!/bin/sh
# A `dump1090` on PATH, for watchdogs/sdr_manager.py (vendored, unmodified) to
# find. Debian (trixie) has no `dump1090` package; it ships `readsb`, the
# maintained successor to dump1090-fa, same CLI family ("--net" enables the
# SBS feed on port 30003, exactly what sdr_manager.py expects). This just
# execs readsb with whatever args sdr_manager.py passed ("--net --quiet",
# falling back to "--net" alone if that exits right away — already handled by
# sdr_manager.py itself, nothing to do here).
#
# Install (needs sudo once):
#   sudo apt install -y rtl-sdr rtl-433 readsb
#   sudo systemctl disable --now readsb   # its own daemon would hold the dongle
#   sudo systemctl mask readsb
#   sudo install -m 755 tools/dump1090-readsb-shim.sh /usr/local/bin/dump1090
#
# See docs/hardware-notes.md and ROADMAP.md (SDR unlock) for the full story.
exec /usr/bin/readsb "$@"
