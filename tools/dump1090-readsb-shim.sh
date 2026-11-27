#!/bin/sh
# A `dump1090` on PATH, for watchdogs/sdr_manager.py (vendored, unmodified) to
# find. Debian (trixie) has no `dump1090` package; it ships `readsb`, the
# maintained successor to dump1090-fa, but without RTL-SDR support compiled
# in (`-Prtlsdr` is off by default upstream) — so we bundle our own build of
# it instead (`vendor/readsb/README.md` has the recipe + provenance) and
# install this shim onto PATH automatically from `packaging/postinst`. No
# manual step needed any more (ROADMAP.md, "SDR unlock").
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
# Prefer the bundled binary (installed next to this script); fall back to a
# system readsb for anyone who still has one hand-built per the old recipe.
READSB_BIN="$(dirname "$(readlink -f "$0")")/readsb"
[ -x "$READSB_BIN" ] || READSB_BIN="/usr/bin/readsb"
exec "$READSB_BIN" --device-type rtlsdr --device 0 --net-sbs-port=30003 "$@"
