#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "Usage: $0 <bundle-dir> <version> <output-path>" >&2
    exit 1
fi

BUNDLE_DIR="$(readlink -f "$1")"
VERSION="$2"
OUTPUT_ARG="$3"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DESKTOP_FILE="$SCRIPT_DIR/io.github.v1rg1lee.svg-to-drawio.desktop"
METAINFO_FILE="$SCRIPT_DIR/io.github.v1rg1lee.svg-to-drawio.metainfo.xml"
ICON_PNG="$REPO_ROOT/svg_to_drawio_desktop/assets/app_logo_256x256.png"
ICON_SVG="$REPO_ROOT/svg_to_drawio_desktop/assets/app_logo.svg"
PACKAGE_NAME="svg-to-drawio"
APP_ID="io.github.v1rg1lee.svg-to-drawio"
ARCHITECTURE="${DEB_ARCHITECTURE:-$(dpkg --print-architecture)}"
MAINTAINER="${DEB_MAINTAINER:-V1rg1lee <noreply@github.com>}"

mkdir -p "$(dirname "$OUTPUT_ARG")"
OUTPUT_DIR="$(cd "$(dirname "$OUTPUT_ARG")" && pwd)"
OUTPUT_PATH="$OUTPUT_DIR/$(basename "$OUTPUT_ARG")"

if [[ ! -d "$BUNDLE_DIR" ]]; then
    echo "Bundle directory not found: $BUNDLE_DIR" >&2
    exit 1
fi

if [[ ! -x "$BUNDLE_DIR/svg-to-drawio" ]]; then
    echo "Expected executable not found in bundle: $BUNDLE_DIR/svg-to-drawio" >&2
    exit 1
fi

required_assets=("$DESKTOP_FILE" "$METAINFO_FILE" "$ICON_PNG" "$ICON_SVG")
missing_assets=()
for asset in "${required_assets[@]}"; do
    if [[ ! -f "$asset" ]]; then
        missing_assets+=("$asset")
    fi
done

if (( ${#missing_assets[@]} > 0 )); then
    echo "Linux packaging assets are incomplete. Missing:" >&2
    printf '  - %s\n' "${missing_assets[@]}" >&2
    exit 1
fi

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
