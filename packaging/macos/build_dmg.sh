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

APP_NAME="$(basename "$APP_BUNDLE")"
VOLUME_NAME="SVG to draw.io"

work_root="$(mktemp -d)"
staging_dir="$work_root/staging"
trap 'rm -rf "$work_root"' EXIT

mkdir -p "$staging_dir"
cp -R "$APP_BUNDLE" "$staging_dir/$APP_NAME"
ln -s /Applications "$staging_dir/Applications"

mkdir -p "$(dirname "$OUTPUT_DMG")"
rm -f "$OUTPUT_DMG"

hdiutil create \
    -volname "$VOLUME_NAME" \
    -srcfolder "$staging_dir" \
    -ov \
    -format UDZO \
    "$OUTPUT_DMG" >/dev/null

echo "Built macOS DMG for SVG to draw.io $VERSION at $OUTPUT_DMG"
