#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [[ $# -ne 3 ]]; then
    echo "Usage: $0 <bundle-dir> <version> <output-path>" >&2
    exit 1
fi

BUNDLE_DIR="$(readlink -f "$1")"
VERSION="$2"
OUTPUT_ARG="$3"
ARCHITECTURE="${DEB_ARCHITECTURE:-$(dpkg --print-architecture)}"
MAINTAINER="${DEB_MAINTAINER:-V1rg1lee <noreply@github.com>}"
OUTPUT_PATH="$(resolve_output_path "$OUTPUT_ARG")"

require_bundle_directory "$BUNDLE_DIR"
require_bundle_entrypoint "$BUNDLE_DIR"
require_files_present \
    "Linux packaging assets are incomplete. Missing:" \
    "$DESKTOP_FILE" \
    "$METAINFO_FILE" \
    "$ICON_PNG" \
    "$ICON_SVG"

if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "dpkg-deb is required to build a .deb package." >&2
    exit 1
fi

PKG_ROOT="$(mktemp -d)"
trap 'rm -rf "$PKG_ROOT"' EXIT

mkdir -p \
    "$PKG_ROOT/DEBIAN" \
    "$PKG_ROOT/opt/$PACKAGE_NAME" \
    "$PKG_ROOT/usr/bin" \
    "$PKG_ROOT/usr/share/applications" \
    "$PKG_ROOT/usr/share/metainfo" \
    "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps" \
    "$PKG_ROOT/usr/share/icons/hicolor/scalable/apps"

cp -a "$BUNDLE_DIR/." "$PKG_ROOT/opt/$PACKAGE_NAME/"
install -m 0644 "$DESKTOP_FILE" "$PKG_ROOT/usr/share/applications/$APP_ID.desktop"
install -m 0644 "$METAINFO_FILE" "$PKG_ROOT/usr/share/metainfo/$APP_ID.metainfo.xml"
install -m 0644 "$ICON_PNG" "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"
install -m 0644 "$ICON_SVG" "$PKG_ROOT/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"

cat > "$PKG_ROOT/usr/bin/svg-to-drawio" <<'EOF'
#!/bin/sh
set -eu
exec /opt/svg-to-drawio/svg-to-drawio "$@"
EOF
chmod 0755 "$PKG_ROOT/usr/bin/svg-to-drawio"

cat > "$PKG_ROOT/DEBIAN/control" <<EOF
Package: $PACKAGE_NAME
Version: $VERSION
Section: graphics
Priority: optional
Architecture: $ARCHITECTURE
Maintainer: $MAINTAINER
Homepage: https://github.com/V1rg1lee/svg-to-drawio
Description: Desktop SVG to draw.io converter
 Convert SVG files into editable draw.io diagrams with a native desktop app.
 This Debian package installs the desktop launcher, application icon, and the
 shared conversion engine under /opt/svg-to-drawio.
EOF

cat > "$PKG_ROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 0755 "$PKG_ROOT/DEBIAN/postinst"

cat > "$PKG_ROOT/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 0755 "$PKG_ROOT/DEBIAN/postrm"

dpkg-deb --build --root-owner-group "$PKG_ROOT" "$OUTPUT_PATH"
