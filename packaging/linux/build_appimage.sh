#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [[ $# -ne 4 ]]; then
    echo "Usage: $0 <binary-path> <version> <appimagetool-path> <output-path>" >&2
    exit 1
fi

BINARY_PATH="$(readlink -f "$1")"
VERSION="$2"
APPIMAGETOOL_PATH="$(readlink -f "$3")"
OUTPUT_ARG="$4"
OUTPUT_PATH="$(resolve_output_path "$OUTPUT_ARG")"

require_binary_file "$BINARY_PATH"

if [[ ! -x "$APPIMAGETOOL_PATH" ]]; then
    echo "appimagetool is missing or not executable: $APPIMAGETOOL_PATH" >&2
    exit 1
fi

require_files_present \
    "Linux packaging assets are incomplete. Missing:" \
    "$DESKTOP_FILE" \
    "$METAINFO_FILE" \
    "$APP_RUN" \
    "$ICON_PNG"

APPDIR_ROOT="$(mktemp -d)"
APPDIR="$APPDIR_ROOT/svg-to-drawio.AppDir"
trap 'rm -rf "$APPDIR_ROOT"' EXIT

mkdir -p \
    "$APPDIR/usr/bin" \
    "$APPDIR/usr/share/applications" \
    "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
    "$APPDIR/usr/share/metainfo"

install -m 0755 "$APP_RUN" "$APPDIR/AppRun"
install -m 0755 "$BINARY_PATH" "$APPDIR/usr/bin/svg-to-drawio"
install -m 0644 "$DESKTOP_FILE" "$APPDIR/$APP_ID.desktop"
install -m 0644 "$DESKTOP_FILE" "$APPDIR/usr/share/applications/$APP_ID.desktop"
install -m 0644 "$ICON_PNG" "$APPDIR/$APP_ID.png"
install -m 0644 "$ICON_PNG" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_ID.png"
install -m 0644 "$METAINFO_FILE" "$APPDIR/usr/share/metainfo/$APP_ID.appdata.xml"

export ARCH="${ARCH:-x86_64}"
export VERSION
export APPIMAGE_EXTRACT_AND_RUN=1

APPIMAGETOOL_ARGS=()
if [[ "${APPIMAGE_SIGN:-0}" == "1" ]]; then
    if ! command -v gpg >/dev/null 2>&1 && ! command -v gpg2 >/dev/null 2>&1; then
        echo "GPG is required when APPIMAGE_SIGN=1." >&2
        exit 1
    fi
    APPIMAGETOOL_ARGS+=(--sign)
fi

"$APPIMAGETOOL_PATH" "${APPIMAGETOOL_ARGS[@]}" "$APPDIR" "$OUTPUT_PATH"
