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
APP_ID="io.github.v1rg1lee.svg-to-drawio"
REMOTE_NAME="${FLATPAK_REMOTE_NAME:-flathub}"
RUNTIME="${FLATPAK_RUNTIME:-org.freedesktop.Platform}"
SDK="${FLATPAK_SDK:-org.freedesktop.Sdk}"
RUNTIME_VERSION="${FLATPAK_RUNTIME_VERSION:-24.08}"
BRANCH="${FLATPAK_BRANCH:-stable}"

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

required_assets=("$DESKTOP_FILE" "$METAINFO_FILE" "$ICON_PNG")
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

if ! command -v flatpak >/dev/null 2>&1 || ! command -v flatpak-builder >/dev/null 2>&1; then
    echo "flatpak and flatpak-builder are required to build a .flatpak bundle." >&2
    exit 1
fi

WORK_ROOT="$(mktemp -d)"
trap 'rm -rf "$WORK_ROOT"' EXIT

SOURCE_DIR="$WORK_ROOT/sources"
PAYLOAD_DIR="$SOURCE_DIR/payload"
BUILD_DIR="$WORK_ROOT/build"
REPO_DIR="$WORK_ROOT/repo"
MANIFEST_FILE="$WORK_ROOT/$APP_ID.json"
mkdir -p "$PAYLOAD_DIR/bundle"
cp -a "$BUNDLE_DIR/." "$PAYLOAD_DIR/bundle/"
cp "$DESKTOP_FILE" "$PAYLOAD_DIR/$APP_ID.desktop"
cp "$METAINFO_FILE" "$PAYLOAD_DIR/$APP_ID.metainfo.xml"
cp "$ICON_PNG" "$PAYLOAD_DIR/$APP_ID.png"
cat > "$PAYLOAD_DIR/launcher.sh" <<'EOF'
#!/bin/sh
set -eu
exec /app/lib/svg-to-drawio/svg-to-drawio "$@"
EOF
chmod 0755 "$PAYLOAD_DIR/launcher.sh"

cat > "$MANIFEST_FILE" <<EOF
{
  "app-id": "$APP_ID",
  "runtime": "$RUNTIME",
  "runtime-version": "$RUNTIME_VERSION",
  "sdk": "$SDK",
  "command": "svg-to-drawio",
  "finish-args": [
    "--share=ipc",
    "--socket=fallback-x11",
    "--socket=wayland",
    "--device=dri",
    "--filesystem=home"
  ],
  "modules": [
    {
      "name": "svg-to-drawio",
      "buildsystem": "simple",
      "build-commands": [
        "mkdir -p /app/lib/svg-to-drawio /app/bin /app/share/applications /app/share/metainfo /app/share/icons/hicolor/256x256/apps",
        "cp -a bundle/. /app/lib/svg-to-drawio/",
        "install -m 0755 launcher.sh /app/bin/svg-to-drawio",
        "install -m 0644 $APP_ID.desktop /app/share/applications/$APP_ID.desktop",
        "install -m 0644 $APP_ID.metainfo.xml /app/share/metainfo/$APP_ID.metainfo.xml",
        "install -m 0644 $APP_ID.png /app/share/icons/hicolor/256x256/apps/$APP_ID.png"
      ],
      "sources": [
        { "type": "dir", "path": "$PAYLOAD_DIR" }
      ]
    }
  ]
}
EOF

flatpak remote-add --user --if-not-exists "$REMOTE_NAME" https://flathub.org/repo/flathub.flatpakrepo
flatpak-builder \
  --force-clean \
  --user \
  --default-branch="$BRANCH" \
  --install-deps-from="$REMOTE_NAME" \
  --repo="$REPO_DIR" \
  "$BUILD_DIR" \
  "$MANIFEST_FILE"

ARCHITECTURE="${FLATPAK_ARCHITECTURE:-$(flatpak --default-arch | tr -d '\r')}"
flatpak build-bundle --arch="$ARCHITECTURE" "$REPO_DIR" "$OUTPUT_PATH" "$APP_ID" "$BRANCH"
