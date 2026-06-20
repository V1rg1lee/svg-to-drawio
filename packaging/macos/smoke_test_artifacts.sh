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
