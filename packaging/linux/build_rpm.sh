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
ICON_SVG="$REPO_ROOT/svg_to_drawio_desktop/assets/app_logo.svg"
LICENSE_FILE="$REPO_ROOT/LICENSE"
PACKAGE_NAME="svg-to-drawio"
APP_ID="io.github.v1rg1lee.svg-to-drawio"
ARCHITECTURE="${RPM_ARCHITECTURE:-$(rpmbuild --eval '%{_arch}' | tr -d '\r' | tail -n 1)}"
PACKAGER="${RPM_PACKAGER:-V1rg1lee <noreply@github.com>}"

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

required_assets=("$DESKTOP_FILE" "$METAINFO_FILE" "$ICON_PNG" "$ICON_SVG" "$LICENSE_FILE")
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

if ! command -v rpmbuild >/dev/null 2>&1; then
    echo "rpmbuild is required to build an .rpm package." >&2
    exit 1
fi

TOPDIR="$(mktemp -d)"
trap 'rm -rf "$TOPDIR"' EXIT
mkdir -p "$TOPDIR"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

SOURCE_ROOT="$TOPDIR/${PACKAGE_NAME}-${VERSION}"
mkdir -p "$SOURCE_ROOT/bundle"
cp -a "$BUNDLE_DIR/." "$SOURCE_ROOT/bundle/"
cp "$DESKTOP_FILE" "$SOURCE_ROOT/$APP_ID.desktop"
cp "$METAINFO_FILE" "$SOURCE_ROOT/$APP_ID.metainfo.xml"
cp "$ICON_PNG" "$SOURCE_ROOT/$APP_ID.png"
cp "$ICON_SVG" "$SOURCE_ROOT/$APP_ID.svg"
cp "$LICENSE_FILE" "$SOURCE_ROOT/LICENSE"
tar -czf "$TOPDIR/SOURCES/${PACKAGE_NAME}-${VERSION}.tar.gz" -C "$TOPDIR" "${PACKAGE_NAME}-${VERSION}"

SPEC_FILE="$TOPDIR/SPECS/${PACKAGE_NAME}.spec"
cat > "$SPEC_FILE" <<EOF
%global debug_package %{nil}
%undefine _debugsource_packages

Name:           $PACKAGE_NAME
Version:        $VERSION
Release:        1%{?dist}
Summary:        Desktop SVG to draw.io converter
License:        MIT
URL:            https://github.com/V1rg1lee/svg-to-drawio
Packager:       $PACKAGER
BuildArch:      $ARCHITECTURE
Source0:        %{name}-%{version}.tar.gz

%description
SVG to draw.io converts SVG files into editable draw.io diagrams with a native desktop application.

%prep
%setup -q

%build

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/opt/%{name}
mkdir -p %{buildroot}/usr/bin
mkdir -p %{buildroot}/usr/share/applications
mkdir -p %{buildroot}/usr/share/metainfo
mkdir -p %{buildroot}/usr/share/icons/hicolor/256x256/apps
mkdir -p %{buildroot}/usr/share/icons/hicolor/scalable/apps
mkdir -p %{buildroot}/usr/share/licenses/%{name}

cp -a bundle/. %{buildroot}/opt/%{name}/
install -m 0644 $APP_ID.desktop %{buildroot}/usr/share/applications/$APP_ID.desktop
install -m 0644 $APP_ID.metainfo.xml %{buildroot}/usr/share/metainfo/$APP_ID.metainfo.xml
install -m 0644 $APP_ID.png %{buildroot}/usr/share/icons/hicolor/256x256/apps/$APP_ID.png
install -m 0644 $APP_ID.svg %{buildroot}/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg
install -m 0644 LICENSE %{buildroot}/usr/share/licenses/%{name}/LICENSE
cat > %{buildroot}/usr/bin/svg-to-drawio <<'LAUNCHER'
#!/bin/sh
set -eu
exec /opt/svg-to-drawio/svg-to-drawio "\$@"
LAUNCHER
chmod 0755 %{buildroot}/usr/bin/svg-to-drawio

%post
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi

%postun
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi

%files
/opt/%{name}
/usr/bin/svg-to-drawio
/usr/share/applications/$APP_ID.desktop
/usr/share/metainfo/$APP_ID.metainfo.xml
/usr/share/icons/hicolor/256x256/apps/$APP_ID.png
/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg
/usr/share/licenses/%{name}/LICENSE

%changelog
* $(date '+%a %b %d %Y') $PACKAGER - $VERSION-1
- Automated release build
EOF

rpmbuild --define "_topdir $TOPDIR" -bb "$SPEC_FILE"

RPM_FILE="$(find "$TOPDIR/RPMS" -type f -name '*.rpm' | head -n 1)"
if [[ -z "$RPM_FILE" ]]; then
    echo "rpmbuild completed without producing an .rpm file." >&2
    exit 1
fi

cp "$RPM_FILE" "$OUTPUT_PATH"
