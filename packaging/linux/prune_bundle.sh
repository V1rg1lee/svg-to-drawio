#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <bundle-dir>" >&2
    exit 1
fi

BUNDLE_DIR="$(readlink -f "$1")"
require_bundle_directory "$BUNDLE_DIR"
prune_optional_qt_plugins "$BUNDLE_DIR"
