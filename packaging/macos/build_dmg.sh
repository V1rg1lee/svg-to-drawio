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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DMG_ICON_PATH="$REPO_ROOT/svg_to_drawio_desktop/assets/VolumeIcon.icns"
DMG_BACKGROUND_PATH="$REPO_ROOT/svg_to_drawio_desktop/assets/dmg_background.png"
APP_NAME="$(basename "$APP_BUNDLE")"
VOLUME_NAME="SVG to draw.io"

work_root="$(mktemp -d)"
staging_dir="$work_root/staging"
read_write_dmg="$work_root/svg-to-drawio-rw.dmg"
mount_dir="$work_root/mount"
mounted_volume=""

cleanup() {
    local exit_status=$?

    if [[ -n "$mounted_volume" ]]; then
        echo "Cleaning up mounted DMG at $mounted_volume" >&2
        if ! hdiutil detach -force "$mounted_volume" -quiet >/dev/null 2>&1; then
            echo "Warning: unable to force-detach $mounted_volume during cleanup." >&2
        fi
    fi

    rm -rf "$work_root"
    trap - EXIT
    exit "$exit_status"
}
trap cleanup EXIT

find_xcode_tool() {
    local tool_name="$1"

    if command -v "$tool_name" >/dev/null 2>&1; then
        command -v "$tool_name"
        return 0
    fi
    if command -v xcrun >/dev/null 2>&1 && xcrun -f "$tool_name" >/dev/null 2>&1; then
        xcrun -f "$tool_name"
        return 0
    fi
    return 1
}

detach_with_retry() {
    local detach_target="$1"
    local attempt
    local max_attempts=6

    for ((attempt = 1; attempt <= max_attempts; attempt++)); do
        if hdiutil detach "$detach_target" -quiet >/dev/null 2>&1; then
            mounted_volume=""
            return 0
        fi

        if ((attempt < max_attempts)); then
            echo "DMG detach attempt $attempt failed; waiting for Finder to flush metadata..."
            sleep 2
        fi
    done

    echo "Unable to detach the writable DMG after $max_attempts attempts." >&2
    return 1
}

mkdir -p "$staging_dir"
cp -R "$APP_BUNDLE" "$staging_dir/$APP_NAME"
ln -s /Applications "$staging_dir/Applications"

SETFILE_BIN=""
if SETFILE_BIN="$(find_xcode_tool SetFile 2>/dev/null)"; then
    echo "Found SetFile at $SETFILE_BIN"
fi

# A DMG can expose two distinct custom icons through two different mechanisms:
#
# 1. Mounted volume icon:
#    .VolumeIcon.icns is stored at the root of the volume, hidden with SetFile
#    -a V, while the volume root carries SetFile -a C ("has custom icon").
#
# 2. Finder icon of the .dmg file before it is mounted:
#    the same source ICNS is converted to an icns resource and appended to the
#    final UDZO file with DeRez/Rez, then SetFile -a C marks that file.
#
# The source artwork is shared, but these mechanisms and their target objects
# are independent. The file-level resource must be applied after hdiutil
# convert, otherwise conversion can discard it.
if [[ -f "$DMG_ICON_PATH" ]]; then
    # Include the icon bytes when hdiutil sizes the writable image. The file is
    # copied again after mounting, where its Finder metadata can be applied
    # reliably to the actual volume filesystem.
    cp "$DMG_ICON_PATH" "$staging_dir/.VolumeIcon.icns"
else
    echo "DMG volume icon not found at $DMG_ICON_PATH; continuing without a custom icon."
fi

if [[ -f "$DMG_BACKGROUND_PATH" ]]; then
    mkdir -p "$staging_dir/.background"
    cp "$DMG_BACKGROUND_PATH" "$staging_dir/.background/dmg_background.png"
    echo "Added Finder background image to .background/dmg_background.png"
else
    echo "DMG background not found at $DMG_BACKGROUND_PATH; skipping Finder styling."
fi

mkdir -p "$(dirname "$OUTPUT_DMG")"
rm -f "$OUTPUT_DMG" "$read_write_dmg"

# Finder writes the window layout and icon positions into .DS_Store, so the
# source image must remain writable until Finder has finished.
hdiutil create \
    -volname "$VOLUME_NAME" \
    -srcfolder "$staging_dir" \
    -ov \
    -format UDRW \
    "$read_write_dmg" >/dev/null

if [[ -f "$DMG_BACKGROUND_PATH" || -f "$DMG_ICON_PATH" ]]; then
    mkdir -p "$mount_dir"
    if ! hdiutil attach \
        "$read_write_dmg" \
        -readwrite \
        -noverify \
        -noautoopen \
        -mountpoint "$mount_dir" >/dev/null; then
        echo "Warning: unable to mount the writable DMG; volume customization was skipped." >&2
    else
        mounted_volume="$mount_dir"

        # Install the mounted-volume icon directly on the writable filesystem.
        # Copying it after attach avoids losing hidden/custom-icon metadata while
        # hdiutil creates the intermediate image from the staging directory.
        if [[ -f "$DMG_ICON_PATH" ]]; then
            if cp "$DMG_ICON_PATH" "$mount_dir/.VolumeIcon.icns"; then
                echo "Added mounted-volume icon as .VolumeIcon.icns"
                if [[ -n "$SETFILE_BIN" ]]; then
                    if ! "$SETFILE_BIN" -c icnC "$mount_dir/.VolumeIcon.icns"; then
                        echo "Warning: unable to set the icon creator code on .VolumeIcon.icns." >&2
                    fi
                    if ! "$SETFILE_BIN" -a V "$mount_dir/.VolumeIcon.icns"; then
                        echo "Warning: unable to hide .VolumeIcon.icns on the mounted volume." >&2
                    fi
                    if ! "$SETFILE_BIN" -a C "$mount_dir"; then
                        echo "Warning: unable to set the custom-icon flag on the mounted volume." >&2
                    fi
                else
                    echo "Warning: SetFile is unavailable; volume icon attributes were not applied." >&2
                fi
            else
                echo "Warning: unable to copy .VolumeIcon.icns to the mounted volume." >&2
            fi
        fi

        if [[ -f "$DMG_BACKGROUND_PATH" ]]; then
            if ! command -v osascript >/dev/null 2>&1; then
                echo "Warning: osascript is unavailable; DMG will lack custom Finder layout." >&2
            else
            # Finder owns the .DS_Store format. Target the exact POSIX mount point
            # instead of looking up a disk by name, which avoids collisions with
            # another mounted volume using the same display name.
                if ! DMG_MOUNT_POINT="$mount_dir" DMG_APP_NAME="$APP_NAME" osascript <<'APPLESCRIPT'
set mountPoint to system attribute "DMG_MOUNT_POINT"
set appName to system attribute "DMG_APP_NAME"
set mountedVolume to POSIX file mountPoint as alias
set backgroundImage to POSIX file (mountPoint & "/.background/dmg_background.png") as alias

tell application "Finder"
    open mountedVolume
    set volumeWindow to container window of mountedVolume
    set current view of volumeWindow to icon view
    set toolbar visible of volumeWindow to false
    set statusbar visible of volumeWindow to false
    set bounds of volumeWindow to {100, 100, 760, 500}

    set viewOptions to the icon view options of volumeWindow
    set arrangement of viewOptions to not arranged
    set icon size of viewOptions to 100
    set background picture of viewOptions to backgroundImage

    set position of item appName of mountedVolume to {160, 185}
    set position of item "Applications" of mountedVolume to {500, 185}

    try
        set extension hidden of item appName of mountedVolume to true
    end try

    update mountedVolume without registering applications
    delay 2
    close volumeWindow
end tell

delay 2
APPLESCRIPT
                then
                    echo "Warning: Finder styling via osascript failed; DMG will lack custom layout." >&2
                else
                    echo "Applied Finder background, window layout, and icon positions."
                fi
            fi

            sync
            if [[ ! -s "$mount_dir/.DS_Store" ]]; then
                echo "Warning: Finder layout metadata (.DS_Store) is missing or empty; DMG may lack custom layout." >&2
            fi
        fi

        sync
        detach_with_retry "$mounted_volume"
    fi
fi

# Convert only after Finder has written and flushed .DS_Store. This preserves
# the customized layout while producing the same compressed read-only UDZO
# format used by previous releases.
hdiutil convert \
    "$read_write_dmg" \
    -ov \
    -format UDZO \
    -o "$OUTPUT_DMG" >/dev/null

# Apply the separate Finder icon for the final .dmg file after conversion.
# Rez/DeRez inject an icns resource into the UDZO file; SetFile marks the file
# as owning a custom icon. This does not replace the mounted-volume icon above.
REZ_BIN=""
DEREZ_BIN=""
if [[ -f "$DMG_ICON_PATH" ]] \
    && [[ -n "$SETFILE_BIN" ]] \
    && REZ_BIN="$(find_xcode_tool Rez 2>/dev/null)" \
    && DEREZ_BIN="$(find_xcode_tool DeRez 2>/dev/null)"; then
    icon_copy="$work_root/dmg_file_icon.icns"
    icon_resource="$work_root/dmg_file_icon.rsrc"
    cp "$DMG_ICON_PATH" "$icon_copy"
    if command -v sips >/dev/null 2>&1; then
        sips -i "$icon_copy" >/dev/null 2>&1 || true
    fi
    "$DEREZ_BIN" -only icns "$icon_copy" > "$icon_resource"
    "$REZ_BIN" -append "$icon_resource" -o "$OUTPUT_DMG"
    "$SETFILE_BIN" -a C "$OUTPUT_DMG" || true
    echo "Applied the custom Finder icon to the final DMG file."
elif [[ -f "$DMG_ICON_PATH" ]]; then
    echo "Warning: SetFile, Rez, or DeRez is unavailable; the DMG file icon was not applied." >&2
fi

# Verify the final file attribute when GetFileInfo is available. This is
# informational only because Xcode command-line tools are optional in local
# builds, and a missing verification tool must not invalidate a usable DMG.
GETFILEINFO_BIN=""
if GETFILEINFO_BIN="$(find_xcode_tool GetFileInfo 2>/dev/null)"; then
    final_attributes=""
    if final_attributes="$("$GETFILEINFO_BIN" -a "$OUTPUT_DMG" 2>/dev/null)"; then
        if [[ "$final_attributes" == *C* ]]; then
            echo "Verified the final DMG custom-icon flag."
        else
            echo "Warning: the final DMG does not report the custom-icon flag." >&2
        fi
    else
        echo "Warning: GetFileInfo could not inspect the final DMG." >&2
    fi
elif [[ -f "$OUTPUT_DMG" ]]; then
    echo "Final DMG exists; GetFileInfo is unavailable, so the custom-icon flag was not verified."
else
    echo "Warning: final DMG verification failed because the output file is missing." >&2
fi

echo "Built macOS DMG for SVG to draw.io $VERSION at $OUTPUT_DMG"
