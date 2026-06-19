#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <version> <package-arch>" >&2
    exit 1
fi

VERSION="$1"
PACKAGE_ARCH="$2"
RELEASE_DIR="$PACKAGING_REPO_ROOT/dist/release"
APPIMAGE_PATH="$RELEASE_DIR/$PACKAGE_NAME-$VERSION-linux-$PACKAGE_ARCH.AppImage"
TAR_PATH="$RELEASE_DIR/$PACKAGE_NAME-$VERSION-linux-$PACKAGE_ARCH.tar.gz"
DEB_PATH="$(find "$RELEASE_DIR" -maxdepth 1 -type f -name "$PACKAGE_NAME-$VERSION-linux-*.deb" | head -n 1)"
RPM_PATH="$(find "$RELEASE_DIR" -maxdepth 1 -type f -name "$PACKAGE_NAME-$VERSION-linux-*.rpm" | head -n 1)"
FLATPAK_PATH="$(find "$RELEASE_DIR" -maxdepth 1 -type f -name "$PACKAGE_NAME-$VERSION-linux-*.flatpak" | head -n 1)"
FEDORA_IMAGE="${FEDORA_IMAGE:-$DEFAULT_FEDORA_IMAGE}"

require_files_present \
    "Linux smoke-test artifacts are incomplete. Missing:" \
    "$APPIMAGE_PATH" \
    "$TAR_PATH" \
    "$DEB_PATH" \
    "$RPM_PATH" \
    "$FLATPAK_PATH"

work_root="$(mktemp -d)"
trap 'rm -rf "$work_root"' EXIT

tar -xzf "$TAR_PATH" -C "$work_root"

tar_executable_path="$work_root/$PACKAGE_NAME"
if [[ -d "$tar_executable_path" ]]; then
    tar_executable_path="$tar_executable_path/$PACKAGE_NAME"
fi

if [[ ! -x "$tar_executable_path" ]]; then
    echo "Unable to find extracted Linux tar smoke-test executable: $tar_executable_path" >&2
    exit 1
fi

"$tar_executable_path" --smoke-test

chmod +x "$APPIMAGE_PATH"
"$APPIMAGE_PATH" --appimage-extract-and-run --smoke-test

sudo dpkg -i "$DEB_PATH"
svg-to-drawio --smoke-test

flatpak uninstall --user --noninteractive -y "$APP_ID" >/dev/null 2>&1 || true
flatpak install --user --noninteractive -y "$FLATPAK_PATH"
flatpak run "$APP_ID" --smoke-test

docker run --rm \
    -e RPM_BASENAME="$(basename "$RPM_PATH")" \
    -v "$RELEASE_DIR:/artifacts:ro" \
    "$FEDORA_IMAGE" \
    bash -lc '
        set -euo pipefail
        dnf install -y --setopt=install_weak_deps=False "/artifacts/$RPM_BASENAME"
        /opt/svg-to-drawio/svg-to-drawio --smoke-test
    '
