"""Regression tests for packaging assets used by release builds."""

from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ICON_PNG = REPO_ROOT / "svg_to_drawio_desktop" / "assets" / "app_logo_256x256.png"
MACOS_DMG_BACKGROUND_PNG = REPO_ROOT / "svg_to_drawio_desktop" / "assets" / "dmg_background.png"
MACOS_DMG_SCRIPT = REPO_ROOT / "packaging" / "macos" / "build_dmg.sh"
MACOS_DMG_SMOKE_TEST = REPO_ROOT / "packaging" / "macos" / "smoke_test_artifacts.sh"
WINDOWS_INSTALLER_SCRIPT = REPO_ROOT / "packaging" / "windows" / "svg-to-drawio.iss"


def _read_png_size(path: Path) -> tuple[int, int]:
    """Return the PNG width and height from its IHDR chunk."""
    with path.open("rb") as handle:
        signature = handle.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise AssertionError(f"{path} is not a valid PNG file.")

        chunk_length = struct.unpack(">I", handle.read(4))[0]
        chunk_type = handle.read(4)
        if chunk_type != b"IHDR":
            raise AssertionError(f"{path} does not start with an IHDR chunk.")
        if chunk_length < 8:
            raise AssertionError(f"{path} has an invalid IHDR chunk length.")

        width, height = struct.unpack(">II", handle.read(8))
        return width, height


def _extract_inno_function(script: str, function_name: str) -> str:
    """Return one Pascal Script function body for structural assertions."""
    match = re.search(
        rf"^function {re.escape(function_name)}\b.*?(?=^function |\Z)",
        script,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Missing Inno Setup function: {function_name}")
    return match.group(0)


class PackagingAssetTests(unittest.TestCase):
    """Validate binary assets required by desktop packaging workflows."""

    def test_linux_application_icon_is_square_256_png(self) -> None:
        """The Linux application icon must be a real 256x256 PNG for AppStream/Flatpak."""
        self.assertTrue(APP_ICON_PNG.is_file(), f"Missing packaging icon: {APP_ICON_PNG}")
        self.assertEqual(_read_png_size(APP_ICON_PNG), (256, 256))

    def test_macos_dmg_background_matches_finder_window_size(self) -> None:
        """The Finder background should use the same 660x400 pixel canvas as its window."""
        self.assertTrue(
            MACOS_DMG_BACKGROUND_PNG.is_file(),
            f"Missing DMG background: {MACOS_DMG_BACKGROUND_PNG}",
        )
        self.assertEqual(_read_png_size(MACOS_DMG_BACKGROUND_PNG), (660, 400))

    def test_macos_dmg_build_uses_native_writable_styling_flow(self) -> None:
        """The DMG script should style a writable image before producing UDZO."""
        script = MACOS_DMG_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("-format UDRW", script)
        self.assertIn("osascript <<'APPLESCRIPT'", script)
        self.assertIn(".background/dmg_background.png", script)
        self.assertIn('DMG_MOUNT_POINT="$mount_dir"', script)
        self.assertIn("set mountedVolume to POSIX file mountPoint as alias", script)
        self.assertIn(
            'set backgroundImage to POSIX file (mountPoint & "/.background/dmg_background.png") as alias',
            script,
        )
        self.assertIn("set background picture of viewOptions to backgroundImage", script)
        self.assertIn("set position of item appName of mountedVolume", script)
        self.assertIn('set position of item "Applications" of mountedVolume', script)
        self.assertIn('if [[ ! -s "$mount_dir/.DS_Store" ]]', script)
        self.assertIn("Finder styling via osascript failed", script)
        self.assertIn("detach_with_retry", script)
        self.assertIn('mounted_device=""', script)
        self.assertIn('mounted_partition=""', script)
        self.assertIn('awk -v mount_point="$mount_dir"', script)
        self.assertIn("sed -E 's/s[0-9]+$//'", script)
        self.assertIn(r"awk '$1 ~ /^\/dev\/disk[0-9]+$/", script)
        self.assertIn('detach_with_retry "${mounted_device:-$mounted_volume}"', script)
        self.assertIn('hdiutil detach -force "$detach_target"', script)
        self.assertIn('if [[ -f "$DMG_ICON_PATH" && ! -s "$mount_dir/.VolumeIcon.icns" ]]', script)
        self.assertIn("-format UDZO", script)

    def test_macos_dmg_build_preserves_both_custom_icon_mechanisms(self) -> None:
        """Mounted-volume and DMG-file icons should both remain configured."""
        script = MACOS_DMG_SCRIPT.read_text(encoding="utf-8")

        finder_close = script.index("close volumeWindow")
        volume_icon_copy = script.index('cp -f "$DMG_ICON_PATH" "$mount_dir/.VolumeIcon.icns"')

        self.assertGreater(volume_icon_copy, finder_close)
        self.assertIn('"$SETFILE_BIN" -c icnC "$mount_dir/.VolumeIcon.icns"', script)
        self.assertIn('"$SETFILE_BIN" -a V "$mount_dir/.VolumeIcon.icns"', script)
        self.assertIn('"$SETFILE_BIN" -a C "$mount_dir"', script)
        self.assertIn('"$DEREZ_BIN" -only icns', script)
        self.assertIn('"$REZ_BIN" -append', script)
        self.assertIn('"$SETFILE_BIN" -a C "$OUTPUT_DMG"', script)
        self.assertIn("find_xcode_tool GetFileInfo", script)

    def test_macos_dmg_smoke_test_validates_volume_icon_metadata(self) -> None:
        """The final DMG should validate the volume icon file and Finder metadata."""
        script = MACOS_DMG_SMOKE_TEST.read_text(encoding="utf-8")

        self.assertIn('! -s "$mount_point/.VolumeIcon.icns"', script)
        self.assertIn('ls -laO "$mount_point"', script)
        self.assertIn('sips -g format "$mount_point/.VolumeIcon.icns"', script)
        self.assertIn('"format: icns"', script)
        self.assertIn("find_xcode_tool GetFileInfo", script)
        self.assertIn('"$GETFILEINFO_BIN" -a "$mount_point/.VolumeIcon.icns"', script)
        self.assertIn('"$GETFILEINFO_BIN" -c "$mount_point/.VolumeIcon.icns"', script)
        self.assertIn('"$GETFILEINFO_BIN" -a "$mount_point"', script)
        self.assertIn('[[ "$icon_attributes" != *V* ]]', script)
        self.assertIn('[[ "$icon_creator" != *icnC* ]]', script)
        self.assertIn('[[ "$volume_attributes" != *C* ]]', script)


class WindowsInstallerSecurityTests(unittest.TestCase):
    """Lock down elevated removal of a previous Windows installation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = WINDOWS_INSTALLER_SCRIPT.read_text(encoding="utf-8")

    def test_uninstall_string_is_read_only_from_hklm(self) -> None:
        lookup = _extract_inno_function(self.script, "GetPreviousUninstallString")

        self.assertIn("RegQueryStringValue(HKLM, uninstallKey, 'UninstallString'", lookup)
        self.assertNotIn("RegQueryStringValue(HKCU", lookup)

    def test_uninstaller_filename_requires_a_nonempty_numeric_suffix(self) -> None:
        filename_validation = _extract_inno_function(self.script, "IsInnoUninstallerFilename")
        digit_validation = _extract_inno_function(self.script, "IsAllDigits")

        self.assertIn("Copy(lowerFileName, 1, 5) <> 'unins'", filename_validation)
        self.assertIn("<> '.exe'", filename_validation)
        self.assertIn("digits := Copy", filename_validation)
        self.assertIn("IsAllDigits(digits)", filename_validation)
        self.assertIn("Length(value) > 0", digit_validation)
        self.assertIn("value[index] < '0'", digit_validation)
        self.assertIn("value[index] > '9'", digit_validation)

    def test_uninstaller_path_must_exist_before_execution(self) -> None:
        path_validation = _extract_inno_function(self.script, "IsValidUninstallerPath")

        self.assertIn("IsInnoUninstallerFilename(ExtractFileName(cleanPath))", path_validation)
        self.assertIn("FileExists(cleanPath)", path_validation)

    def test_invalid_uninstaller_fails_closed_with_user_message(self) -> None:
        uninstall = _extract_inno_function(self.script, "UninstallPreviousVersion")
        invalid_start = uninstall.index("if not IsValidUninstallerPath")
        valid_execution = uninstall.index("Log('Removing previous version", invalid_start)
        invalid_block = uninstall[invalid_start:valid_execution]

        self.assertIn("SuppressibleMsgBox", invalid_block)
        self.assertIn("Please uninstall it manually", invalid_block)
        self.assertIn("Result := False", invalid_block)
        self.assertLess(invalid_block.index("Result := False"), invalid_block.index("exit;"))

    def test_uninstaller_is_parsed_and_validated_before_exec(self) -> None:
        uninstall = _extract_inno_function(self.script, "UninstallPreviousVersion")

        parse_index = uninstall.index("ExtractUninstallerPath")
        validation_index = uninstall.index("IsValidUninstallerPath")
        exec_index = uninstall.index("Exec(")
        self.assertLess(parse_index, validation_index)
        self.assertLess(validation_index, exec_index)
        self.assertNotIn("RemoveQuotes", uninstall)
        self.assertIn("'/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-'", uninstall)


if __name__ == "__main__":
    unittest.main()
