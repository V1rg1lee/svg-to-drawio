#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <version>" >&2
    exit 1
fi

VERSION="$1"

CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-docker}"
FEDORA_IMAGE="${FEDORA_IMAGE:-$DEFAULT_FEDORA_IMAGE}"
FEDORA_PYTHON="${FEDORA_PYTHON:-python3}"
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

runtime_binary="${CONTAINER_RUNTIME%% *}"
if ! command -v "$runtime_binary" >/dev/null 2>&1; then
    echo "Container runtime not found: $runtime_binary" >&2
    exit 1
fi

mkdir -p "$PACKAGING_REPO_ROOT/dist/release"

${CONTAINER_RUNTIME} run --rm \
    -e HOST_UID="$HOST_UID" \
    -e HOST_GID="$HOST_GID" \
    -e VERSION="$VERSION" \
    -e FEDORA_PYTHON="$FEDORA_PYTHON" \
    -v "$PACKAGING_REPO_ROOT:/workspace" \
    -w /workspace \
    "$FEDORA_IMAGE" \
    bash -lc '
        set -euo pipefail
        source packaging/linux/common.sh

        dnf install -y --setopt=install_weak_deps=False \
            findutils \
            gzip \
            rpm-build \
            tar \
            python3 \
            python3-pip

        "$FEDORA_PYTHON" -m pip install --upgrade pip
        "$FEDORA_PYTHON" -m pip install -r requirements-desktop.txt

        "$FEDORA_PYTHON" build_desktop.py --bundle-mode onedir --dist-dir dist/desktop-rpm-package

        BUNDLE_ROOT="dist/desktop-rpm-package/svg-to-drawio"
        prune_optional_qt_plugins "$BUNDLE_ROOT"

        RPM_ARCH="$(rpmbuild --eval "%{_arch}" | tr -d "\r" | tail -n 1)"
        chmod +x packaging/linux/build_rpm.sh
        packaging/linux/build_rpm.sh \
            "$BUNDLE_ROOT" \
            "$VERSION" \
            "dist/release/svg-to-drawio-${VERSION}-linux-${RPM_ARCH}.rpm"

        chown -R "$HOST_UID:$HOST_GID" build dist
    '
