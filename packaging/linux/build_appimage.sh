#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
    echo "Usage: $0 <binary-path> <version> <appimagetool-path> <output-path>" >&2
    exit 1
fi

BINARY_PATH="$(readlink -f "$1")"
VERSION="$2"
APPIMAGETOOL_PATH="$(readlink -f "$3")"
OUTPUT_ARG="$4"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DESKTOP_FILE="$SCRIPT_DIR/io.github.v1rg1lee.svg-to-drawio.desktop"
APP_RUN="$SCRIPT_DIR/AppRun"
ICON_FILE="$REPO_ROOT/svg_to_drawio_desktop/assets/app_logo_256x256.png"
mkdir -p "$(dirname "$OUTPUT_ARG")"
OUTPUT_DIR="$(cd "$(dirname "$OUTPUT_ARG")" && pwd)"
OUTPUT_PATH="$OUTPUT_DIR/$(basename "$OUTPUT_ARG")"

if [[ ! -f "$BINARY_PATH" ]]; then
    echo "Binary not found: $BINARY_PATH" >&2
    exit 1
fi

if [[ ! -x "$APPIMAGETOOL_PATH" ]]; then
    echo "appimagetool is missing or not executable: $APPIMAGETOOL_PATH" >&2
    exit 1
fi

if [[ ! -f "$DESKTOP_FILE" || ! -f "$APP_RUN" || ! -f "$ICON_FILE" ]]; then
    echo "Linux packaging assets are incomplete." >&2
    exit 1
fi

APPDIR_ROOT="$(mktemp -d)"
APPDIR="$APPDIR_ROOT/svg-to-drawio.AppDir"
trap 'rm -rf "$APPDIR_ROOT"' EXIT

mkdir -p \
    "$APPDIR/usr/bin" \
    "$APPDIR/usr/share/applications" \
    "$APPDIR/usr/share/icons/hicolor/256x256/apps"

install -m 0755 "$APP_RUN" "$APPDIR/AppRun"
install -m 0755 "$BINARY_PATH" "$APPDIR/usr/bin/svg-to-drawio"
install -m 0644 "$DESKTOP_FILE" "$APPDIR/io.github.v1rg1lee.svg-to-drawio.desktop"
install -m 0644 "$DESKTOP_FILE" "$APPDIR/usr/share/applications/io.github.v1rg1lee.svg-to-drawio.desktop"
install -m 0644 "$ICON_FILE" "$APPDIR/io.github.v1rg1lee.svg-to-drawio.png"
install -m 0644 "$ICON_FILE" "$APPDIR/usr/share/icons/hicolor/256x256/apps/io.github.v1rg1lee.svg-to-drawio.png"

export ARCH="${ARCH:-x86_64}"
export VERSION
export APPIMAGE_EXTRACT_AND_RUN=1

"$APPIMAGETOOL_PATH" "$APPDIR" "$OUTPUT_PATH"
