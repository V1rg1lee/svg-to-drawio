#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <version>" >&2
    exit 1
fi

VERSION="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DMG_PATH="$REPO_ROOT/dist/release/svg-to-drawio-$VERSION-macos.dmg"
APP_BUNDLE_NAME="SVG to draw.io.app"
APP_EXECUTABLE_NAME="SVG to draw.io"
APP_EXECUTABLE="$REPO_ROOT/dist/desktop/$APP_BUNDLE_NAME/Contents/MacOS/$APP_EXECUTABLE_NAME"
DMG_BACKGROUND_SOURCE="$REPO_ROOT/svg_to_drawio_desktop/assets/dmg_background.png"
DMG_ICON_SOURCE="$REPO_ROOT/svg_to_drawio_desktop/assets/VolumeIcon.icns"

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

if [[ ! -x "$APP_EXECUTABLE" || ! -f "$DMG_PATH" ]]; then
    echo "macOS smoke-test artifacts are incomplete." >&2
    exit 1
fi

"$APP_EXECUTABLE" --smoke-test

mount_point="$(mktemp -d)"
cleanup() {
    hdiutil detach "$mount_point" -quiet >/dev/null 2>&1 || true
    rm -rf "$mount_point"
}
trap cleanup EXIT

hdiutil attach "$DMG_PATH" -nobrowse -readonly -mountpoint "$mount_point" >/dev/null
"$mount_point/$APP_BUNDLE_NAME/Contents/MacOS/$APP_EXECUTABLE_NAME" --smoke-test

if [[ -f "$DMG_BACKGROUND_SOURCE" ]]; then
    if [[ ! -f "$mount_point/.background/dmg_background.png" ]]; then
        echo "Warning: the packaged DMG is missing its Finder background image." >&2
    fi
    if [[ ! -f "$mount_point/.DS_Store" ]]; then
        echo "Warning: the packaged DMG is missing the Finder layout metadata." >&2
    fi
fi

if [[ -f "$DMG_ICON_SOURCE" && ! -s "$mount_point/.VolumeIcon.icns" ]]; then
    echo "The packaged DMG is missing its mounted-volume icon." >&2
    echo "Mounted DMG root contents:" >&2
    ls -laO "$mount_point" >&2
    exit 1
fi

if [[ -f "$DMG_ICON_SOURCE" ]]; then
    GETFILEINFO_BIN=""
    if ! GETFILEINFO_BIN="$(find_xcode_tool GetFileInfo 2>/dev/null)"; then
        echo "GetFileInfo is required to validate the packaged DMG volume icon." >&2
        exit 1
    fi

    icon_attributes="$("$GETFILEINFO_BIN" -a "$mount_point/.VolumeIcon.icns")"
    if [[ "$icon_attributes" != *V* ]]; then
        echo "The packaged DMG volume icon is not marked invisible (missing V attribute)." >&2
        echo "Reported icon attributes: $icon_attributes" >&2
        exit 1
    fi

    icon_creator="$("$GETFILEINFO_BIN" -c "$mount_point/.VolumeIcon.icns")"
    if [[ "$icon_creator" != *icnC* ]]; then
        echo "The packaged DMG volume icon does not use the icnC creator code." >&2
        echo "Reported icon creator: $icon_creator" >&2
        exit 1
    fi

    volume_attributes="$("$GETFILEINFO_BIN" -a "$mount_point")"
    if [[ "$volume_attributes" != *C* ]]; then
        echo "The packaged DMG volume is not marked as having a custom icon (missing C attribute)." >&2
        echo "Reported volume attributes: $volume_attributes" >&2
        exit 1
    fi

    echo "Verified mounted-volume icon metadata: invisible V, creator icnC, custom-volume C."
fi
