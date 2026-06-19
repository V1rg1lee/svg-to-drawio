#!/usr/bin/env bash
set -euo pipefail

PACKAGING_LINUX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGING_REPO_ROOT="$(cd "$PACKAGING_LINUX_DIR/../.." && pwd)"

APP_ID="io.github.v1rg1lee.svg-to-drawio"
PACKAGE_NAME="svg-to-drawio"
DESKTOP_FILE="$PACKAGING_LINUX_DIR/$APP_ID.desktop"
METAINFO_FILE="$PACKAGING_LINUX_DIR/$APP_ID.metainfo.xml"
APP_RUN="$PACKAGING_LINUX_DIR/AppRun"
ICON_PNG="$PACKAGING_REPO_ROOT/svg_to_drawio_desktop/assets/app_logo_256x256.png"
ICON_SVG="$PACKAGING_REPO_ROOT/svg_to_drawio_desktop/assets/app_logo.svg"
LICENSE_FILE="$PACKAGING_REPO_ROOT/LICENSE"

# Single source of truth for the Fedora image used both to build the RPM and to smoke-test
# it afterwards - keeping the build and test environments on the same release matters more
# than always tracking the latest Fedora, so bump this in one place rather than per-script.
DEFAULT_FEDORA_IMAGE="fedora:42"


resolve_output_path() {
    local raw_output="$1"
    mkdir -p "$(dirname "$raw_output")"
    local output_dir
    output_dir="$(cd "$(dirname "$raw_output")" && pwd)"
    printf '%s/%s\n' "$output_dir" "$(basename "$raw_output")"
}


require_bundle_directory() {
    local bundle_dir="$1"
    if [[ ! -d "$bundle_dir" ]]; then
        echo "Bundle directory not found: $bundle_dir" >&2
        exit 1
    fi
}


require_bundle_entrypoint() {
    local bundle_dir="$1"
    local executable_name="${2:-svg-to-drawio}"
    if [[ ! -x "$bundle_dir/$executable_name" ]]; then
        echo "Expected executable not found in bundle: $bundle_dir/$executable_name" >&2
        exit 1
    fi
}


require_binary_file() {
    local binary_path="$1"
    if [[ ! -f "$binary_path" ]]; then
        echo "Binary not found: $binary_path" >&2
        exit 1
    fi
}


require_files_present() {
    local header="$1"
    shift
    local missing_assets=()
    local asset
    for asset in "$@"; do
        if [[ ! -f "$asset" ]]; then
            missing_assets+=("$asset")
        fi
    done

    if (( ${#missing_assets[@]} > 0 )); then
        echo "$header" >&2
        printf '  - %s\n' "${missing_assets[@]}" >&2
        exit 1
    fi
}


prune_optional_qt_plugins() {
    local bundle_root="$1"
    local qt_plugins_dir="$bundle_root/_internal/PySide6/Qt/plugins"
    if [[ ! -d "$qt_plugins_dir" ]]; then
        return
    fi

    # These plugins are not needed by this app and tend to drag in distro-specific
    # runtime dependencies that make Linux packages less portable.
    rm -f "$qt_plugins_dir/imageformats/libqtiff.so"
    rm -f "$qt_plugins_dir/platformthemes/libqgtk3.so"
    rm -f "$qt_plugins_dir/platforms/libqminimal.so" "$qt_plugins_dir/platforms/libqvnc.so"
    rm -f "$qt_plugins_dir/xcbglintegrations/"*.so
    rm -f "$qt_plugins_dir/generic/libqevdev"*.so
}
