#!/usr/bin/env bash
# Build an APPLaunch-compatible .deb for sideloading, following M5's
# AppBuilder packaging conventions (docs/launcher-guidelines.md) — a trimmed
# adaptation of CardputerZero/AppBuilder's own scripts/pack-deb.sh (MIT),
# simplified for this repo's single app (no multi-example discovery, no
# build.sh compile step — nothing here needs compiling).
#
# Usage: tools/pack-deb.sh [--output-dir DIR]
#
# Produces $OUTPUT_DIR/<pkg>_<version>-<revision>_arm64.deb from
# packaging/{meta.env,stage.sh,postinst,icon.png} (run from the repo root).
#
# APPLaunch runtime layout (docs/launcher-guidelines.md):
#   /usr/share/APPLaunch/
#       applications/<pkg>.desktop
#       bin/<pkg>                    (the launcher wrapper stage.sh installs)
#       apps/<pkg>/...               (the app's own files, incl. vendor/)
#       share/images/<pkg>.png
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PKG_DIR="$REPO_ROOT/packaging"

OUTPUT_DIR="$REPO_ROOT/dist"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

if [[ ! -f "$PKG_DIR/meta.env" ]]; then
    echo "error: $PKG_DIR/meta.env missing" >&2
    exit 1
fi
# shellcheck disable=SC1091
source "$PKG_DIR/meta.env"

: "${PKG_NAME:?PKG_NAME required in packaging/meta.env}"
: "${PKG_VERSION:?PKG_VERSION required}"
: "${PKG_REVISION:=1}"
: "${PKG_DESC:?PKG_DESC required}"
: "${PKG_DEPENDS:=}"
: "${PKG_RECOMMENDS:=}"
: "${APP_NAME:=$PKG_NAME}"
: "${APP_EXEC:?APP_EXEC required (absolute path)}"
: "${APP_TERMINAL:=false}"
: "${APP_ICON:=share/images/${PKG_NAME}.png}"

ARCH="arm64"
INSTALL_PREFIX="/usr/share/APPLaunch"
APP_INSTALL_DIR="$INSTALL_PREFIX/apps/$PKG_NAME"

mkdir -p "$OUTPUT_DIR"
echo "==[ $PKG_NAME $PKG_VERSION-$PKG_REVISION ($ARCH) ]=="

STAGE="$(mktemp -d -t pack-deb-XXXXXXXX)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p \
    "$STAGE/DEBIAN" \
    "$STAGE$INSTALL_PREFIX/applications" \
    "$STAGE$INSTALL_PREFIX/bin" \
    "$STAGE$INSTALL_PREFIX/share/images" \
    "$STAGE$APP_INSTALL_DIR"

if [[ -f "$PKG_DIR/icon.png" ]]; then
    cp "$PKG_DIR/icon.png" "$STAGE$INSTALL_PREFIX/share/images/${PKG_NAME}.png"
fi

echo "-- stage.sh"
export STAGE INSTALL_PREFIX APP_INSTALL_DIR PKG_NAME
( cd "$REPO_ROOT" && bash "$PKG_DIR/stage.sh" )

echo "-- .desktop"
cat > "$STAGE$INSTALL_PREFIX/applications/${PKG_NAME}.desktop" <<EOF
[Desktop Entry]
Name=$APP_NAME
Exec=$APP_EXEC
Terminal=$APP_TERMINAL
Icon=$APP_ICON
Type=Application
EOF

echo "-- DEBIAN/control"
PACKAGED_DATE="$(date -u '+%Y-%m-%d %H:%M:%S')"
{
    echo "Package: $PKG_NAME"
    echo "Version: $PKG_VERSION-$PKG_REVISION"
    echo "Architecture: $ARCH"
    echo "Maintainer: ${PKG_MAINTAINER:-WatchDogsGo-CardPZero <noreply@example.com>}"
    echo "Section: APPLaunch"
    echo "Priority: optional"
    echo "Homepage: ${PKG_HOMEPAGE:-https://github.com/LOCOSP/WatchDogsGo}"
    echo "Packaged-Date: $PACKAGED_DATE"
    if [[ -n "$PKG_DEPENDS" ]]; then echo "Depends: $PKG_DEPENDS"; fi
    if [[ -n "$PKG_RECOMMENDS" ]]; then echo "Recommends: $PKG_RECOMMENDS"; fi
    echo "Description: $PKG_DESC"
} > "$STAGE/DEBIAN/control"

for hook in postinst prerm postrm preinst; do
    if [[ -f "$PKG_DIR/$hook" ]]; then
        cp "$PKG_DIR/$hook" "$STAGE/DEBIAN/$hook"
        chmod 0755 "$STAGE/DEBIAN/$hook"
    fi
done

find "$STAGE$INSTALL_PREFIX/bin" -type f -exec chmod 0755 {} \;

OUT_FILE="$OUTPUT_DIR/${PKG_NAME}_${PKG_VERSION}-${PKG_REVISION}_${ARCH}.deb"
DPKG_ARGS=(-b "$STAGE" "$OUT_FILE")
if dpkg-deb --help 2>/dev/null | grep -q -- '--root-owner-group'; then
    DPKG_ARGS=(--root-owner-group "${DPKG_ARGS[@]}")
fi
dpkg-deb "${DPKG_ARGS[@]}"

echo "-- built: $OUT_FILE"
dpkg-deb --info "$OUT_FILE"
