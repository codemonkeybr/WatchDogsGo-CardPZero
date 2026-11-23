#!/usr/bin/env bash
# Called by tools/pack-deb.sh (STAGE/INSTALL_PREFIX/APP_INSTALL_DIR/PKG_NAME
# are already exported) from the repo root. Copies the vendored game +
# platform layer into $APP_INSTALL_DIR, bundles pyxel/LoRaRF (not in Debian,
# ROADMAP "Still open") as plain unzipped wheels under vendor/ instead of a
# venv, and installs the launcher wrapper.
set -euo pipefail

REPO_ROOT="$(pwd)"
DEST="$STAGE$APP_INSTALL_DIR"

echo "-- copying app files"
mkdir -p "$DEST"
for item in watchdogs plugins czplatform assets wdg_wifi_bridge.py hs_capture.py \
            secrets.conf.example LICENSE; do
    cp -a "$REPO_ROOT/$item" "$DEST/"
done
# dev-only cruft that may have been left behind under assets/ or elsewhere
find "$DEST" -name "__pycache__" -type d -prune -exec rm -rf {} +

# dump1090-readsb-shim.sh isn't runnable as shipped (Debian's readsb lacks
# RTL-SDR support, so it needs a hand-built readsb first — docs/install.md),
# but ship it anyway so the manual ADS-B step has something to install.
mkdir -p "$DEST/tools"
cp -a "$REPO_ROOT/tools/dump1090-readsb-shim.sh" "$DEST/tools/"

echo "-- vendoring pyxel + LoRaRF (not packaged for Debian)"
VENDOR_DIR="$DEST/vendor"
mkdir -p "$VENDOR_DIR"
WHEEL_TMP="$(mktemp -d)"
trap 'rm -rf "$WHEEL_TMP"' EXIT

pip download pyxel==3.0.2 --no-deps --only-binary=:all: \
    --platform manylinux_2_28_aarch64 --python-version 313 \
    --implementation cp --abi cp313 -d "$WHEEL_TMP"
pip download LoRaRF==1.4.0 --no-deps --only-binary=:all: \
    --platform any --python-version 313 --implementation py \
    -d "$WHEEL_TMP"

for whl in "$WHEEL_TMP"/*.whl; do
    python3 -m zipfile -e "$whl" "$VENDOR_DIR"
done
# wheel metadata (.dist-info/RECORD etc.) isn't needed at runtime
rm -rf "$VENDOR_DIR"/*.dist-info

echo "-- installing launcher wrapper"
WRAPPER="$STAGE$INSTALL_PREFIX/bin/$PKG_NAME"
mkdir -p "$(dirname "$WRAPPER")"
cat > "$WRAPPER" <<EOF
#!/bin/sh
# cwd must be writable: lgpio (RPi.GPIO's backend, used by LoRaRF) opens its
# notify pipe at a path relative to cwd, and \$APP_INSTALL_DIR is root-owned
# and read-only once installed. \`python3 -m czplatform\` itself resolves the
# czplatform package through sys.path (cwd for \`-m\`, or PYTHONPATH), not
# through the cwd-independent sys.path.insert czplatform/__main__.py does
# once already running — so APP_INSTALL_DIR has to stay on PYTHONPATH even
# though cwd moves to the writable data dir.
DATA_DIR="\$HOME/.local/share/$PKG_NAME"
mkdir -p "\$DATA_DIR"
export PYTHONPATH="$APP_INSTALL_DIR:$APP_INSTALL_DIR/vendor\${PYTHONPATH:+:\$PYTHONPATH}"
cd "\$DATA_DIR"
exec python3 -m czplatform --canvas 320x170 --data-dir "\$DATA_DIR"
EOF
chmod 0755 "$WRAPPER"
