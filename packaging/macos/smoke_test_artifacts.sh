#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <version>" >&2
    exit 1
fi

VERSION="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ZIP_PATH="$REPO_ROOT/dist/release/svg-to-drawio-$VERSION-macos.zip"
APP_EXECUTABLE="$REPO_ROOT/dist/desktop/svg-to-drawio.app/Contents/MacOS/svg-to-drawio"

if [[ ! -x "$APP_EXECUTABLE" || ! -f "$ZIP_PATH" ]]; then
    echo "macOS smoke-test artifacts are incomplete." >&2
    exit 1
fi

"$APP_EXECUTABLE" --smoke-test

work_root="$(mktemp -d)"
trap 'rm -rf "$work_root"' EXIT
ditto -x -k "$ZIP_PATH" "$work_root"
"$work_root/svg-to-drawio.app/Contents/MacOS/svg-to-drawio" --smoke-test
