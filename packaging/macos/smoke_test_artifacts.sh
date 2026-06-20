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
