#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "Usage: $0 <app-bundle> <version> <output-dmg>" >&2
    exit 1
fi

APP_BUNDLE="$1"
VERSION="$2"
OUTPUT_DMG="$3"

if [[ ! -d "$APP_BUNDLE" || "${APP_BUNDLE##*.}" != "app" ]]; then
    echo "Expected a macOS .app bundle, got: $APP_BUNDLE" >&2
    exit 1
fi

if ! command -v hdiutil >/dev/null 2>&1; then
    echo "hdiutil is required to build a macOS DMG." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DMG_ICON_PATH="$REPO_ROOT/svg_to_drawio_desktop/assets/dmg_volume.icns"
APP_NAME="$(basename "$APP_BUNDLE")"
VOLUME_NAME="SVG to draw.io"

work_root="$(mktemp -d)"
staging_dir="$work_root/staging"
trap 'rm -rf "$work_root"' EXIT

mkdir -p "$staging_dir"
cp -R "$APP_BUNDLE" "$staging_dir/$APP_NAME"
ln -s /Applications "$staging_dir/Applications"

find_xcode_tool() {
    local tool_name="$1"

    if command -v "$tool_name" >/dev/null 2>&1; then
        command -v "$tool_name"
        return 0
    fi
    if command -v xcrun >/dev/null 2>&1 && xcrun -f "$tool_name" >/dev/null 2>&1; then
        xcrun -f "$tool_name"
        return 0
    fi
    return 1
}

SETFILE_BIN=""
if SETFILE_BIN="$(find_xcode_tool SetFile 2>/dev/null)" && [[ -f "$DMG_ICON_PATH" ]]; then
    cp "$DMG_ICON_PATH" "$staging_dir/.VolumeIcon.icns"
    "$SETFILE_BIN" -a C "$staging_dir" || true
    "$SETFILE_BIN" -a V "$staging_dir/.VolumeIcon.icns" || true
fi

mkdir -p "$(dirname "$OUTPUT_DMG")"
rm -f "$OUTPUT_DMG"

hdiutil create \
    -volname "$VOLUME_NAME" \
    -srcfolder "$staging_dir" \
    -ov \
    -format UDZO \
    "$OUTPUT_DMG" >/dev/null

REZ_BIN=""
DEREZ_BIN=""
if [[ -f "$DMG_ICON_PATH" ]] \
    && SETFILE_BIN="$(find_xcode_tool SetFile 2>/dev/null)" \
    && REZ_BIN="$(find_xcode_tool Rez 2>/dev/null)" \
    && DEREZ_BIN="$(find_xcode_tool DeRez 2>/dev/null)"; then
    icon_copy="$work_root/dmg_file_icon.icns"
    icon_resource="$work_root/dmg_file_icon.rsrc"
    cp "$DMG_ICON_PATH" "$icon_copy"
    if command -v sips >/dev/null 2>&1; then
        sips -i "$icon_copy" >/dev/null 2>&1 || true
    fi
    "$DEREZ_BIN" -only icns "$icon_copy" > "$icon_resource"
    "$REZ_BIN" -append "$icon_resource" -o "$OUTPUT_DMG"
    "$SETFILE_BIN" -a C "$OUTPUT_DMG" || true
fi

echo "Built macOS DMG for SVG to draw.io $VERSION at $OUTPUT_DMG"
