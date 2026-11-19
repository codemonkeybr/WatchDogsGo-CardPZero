#!/bin/sh
# A `dump1090` on PATH, for watchdogs/sdr_manager.py (vendored, unmodified) to
# find. Debian (trixie) has no `dump1090` package; it ships `readsb`, the
# maintained successor to dump1090-fa, built here from Debian's own source with
# its `-Prtlsdr` profile (see ROADMAP.md, "SDR unlock") so RTL-SDR support is
# actually compiled in.
#
# This readsb build differs from legacy dump1090 in two ways sdr_manager.py's
# hard-coded `["dump1090", "--net", "--quiet"]` doesn't account for (can't
# change that file — it's vendored unmodified):
#   - it needs an explicit `--device-type rtlsdr --device <index>` (old
#     dump1090 just assumed an RTL-SDR and auto-indexed);
#   - `--net` alone no longer opens the SBS port on 30003 by default
#     (`--net-sbs-port` defaults to 0) — sdr_manager.py's `_sbs_reader` thread
#     connects to 30003, so it must be requested explicitly.
# Both are added here instead, so the vendored command line keeps working
# as-is. Device index: sdr_manager.py runs rtl_433 on index 1 only when
# dump1090 is already running (two-dongle setups); with one dongle (the usual
# case here), always use index 0 and never run ADS-B and 433 MHz at once.
#
# Install (needs sudo once):
#   sudo apt install -y --no-install-recommends \
#       devscripts dpkg-dev debhelper \
#       libusb-1.0-0-dev libncurses-dev zlib1g-dev zlib1g pkg-config \
#       libzstd-dev libzstd1 librtlsdr0 librtlsdr-dev rtl-sdr rtl-433
#   sudo systemctl disable --now readsb   # its own daemon would hold the dongle
#   sudo systemctl mask readsb
#   mkdir -p /tmp/readsb-build && cd /tmp/readsb-build
#   dget -u https://deb.debian.org/debian/pool/main/r/readsb/readsb_3.14.1630+git20240609.adc080d-1.dsc
#   cd readsb-3.14.1630+git20240609.adc080d
#   DEB_BUILD_OPTIONS=noddebs dpkg-buildpackage -b -Prtlsdr -ui -uc -us
#   cd .. && sudo dpkg -i readsb_3.14.1630+git20240609.adc080d-1_arm64.deb
#   sudo install -m 755 tools/dump1090-readsb-shim.sh /usr/local/bin/dump1090
#
# See docs/hardware-notes.md and ROADMAP.md (SDR unlock) for the full story.
exec /usr/bin/readsb --device-type rtlsdr --device 0 --net-sbs-port=30003 "$@"
