"""Build desktop bundles with PyInstaller."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path


def _add_data_argument(source: Path, destination: str) -> str:
    """Return one PyInstaller --add-data argument for the current platform."""
    separator = ";" if sys.platform == "win32" else ":"
    return f"{source}{separator}{destination}"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the desktop bundle build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle-mode",
        choices=("auto", "onefile", "onedir"),
        default="auto",
        help="PyInstaller layout to build. Defaults to onedir on macOS and onefile elsewhere.",
    )
    parser.add_argument(
        "--dist-dir",
        default="dist/desktop",
        help="Output directory for the built bundle, relative to the repository root by default.",
    )
    return parser.parse_args(argv)


def _resolve_bundle_mode(bundle_mode: str) -> str:
    """Resolve the effective PyInstaller bundle mode for this platform."""
    if bundle_mode != "auto":
        return bundle_mode
    # macOS requires a .app bundle; Windows/Linux default to a portable onefile build.
    return "onedir" if sys.platform == "darwin" else "onefile"


def _resolve_path(project_root: Path, raw_path: str) -> Path:
    """Resolve an absolute or repository-relative path."""
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _generate_icns(png_path: Path, output_path: Path) -> bool:
    """Generate a .icns bundle from a PNG using macOS sips + iconutil.

    Both tools ship with every macOS installation - no extra dependency needed.
    Returns True on success, False if a tool is unavailable or fails.
    """
    import shutil

    if not (shutil.which("sips") and shutil.which("iconutil")):
        return False

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "app.iconset"
        iconset.mkdir()

        for size in (16, 32, 64, 128, 256, 512):
            for scale, suffix in ((1, ""), (2, "@2x")):
                px = size * scale
                out = iconset / f"icon_{size}x{size}{suffix}.png"
                result = subprocess.run(
                    ["sips", "-z", str(px), str(px), str(png_path), "--out", str(out)],
                    capture_output=True,
                )
                if result.returncode != 0:
                    return False

        result = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(output_path)],
            capture_output=True,
        )
        return result.returncode == 0 and output_path.is_file()


def main(argv: Sequence[str] | None = None) -> None:
    """Build the base desktop executable or app bundle."""
    from PyInstaller.__main__ import run as pyinstaller_run

    options = _parse_args(argv)
    project_root = Path(__file__).resolve().parent
    bundle_mode = _resolve_bundle_mode(options.bundle_mode)
    build_root = project_root / "build" / "pyinstaller" / bundle_mode
    dist_root = _resolve_path(project_root, options.dist_dir)
    assets_dir = project_root / "svg_to_drawio_desktop" / "assets"

    args = [
        str(project_root / "desktop_app.py"),
        "--noconfirm",
        "--clean",
        "--windowed",
        f"--{bundle_mode}",
        "--name",
        "svg-to-drawio",
        "--paths",
        str(project_root),
        "--distpath",
        str(dist_root),
        "--workpath",
        str(build_root / "work"),
        "--specpath",
        str(build_root / "spec"),
    ]

    # Bundle all runtime assets (PNG, ICO, SVG, and similar files).
    for asset_path in assets_dir.iterdir():
        if asset_path.is_file():
            args.extend(["--add-data", _add_data_argument(asset_path, "svg_to_drawio_desktop/assets")])

    # Apply platform-specific application icons where PyInstaller supports them.
    if sys.platform == "win32":
        # Windows: multi-resolution ICO (native format).
        ico_path = assets_dir / "app_logo.ico"
        if ico_path.is_file():
            args.extend(["--icon", str(ico_path)])

    elif sys.platform == "darwin":
        # macOS: .icns required.  Prefer a pre-built file; generate from PNG if absent.
        icns_path = assets_dir / "app_logo.icns"
        if not icns_path.is_file():
            png_path = assets_dir / "app_logo_256x256.png"
            if png_path.is_file():
                build_root.mkdir(parents=True, exist_ok=True)
                generated = build_root / "app_logo.icns"
                if _generate_icns(png_path, generated):
                    icns_path = generated
                    print(f"[build] Generated {icns_path}")
                else:
                    print("[build] Warning: could not generate .icns - app will use default icon.")
                    icns_path = None
        if icns_path and icns_path.is_file():
            args.extend(["--icon", str(icns_path)])
        args.extend(["--osx-bundle-identifier", "io.github.v1rg1lee.svg-to-drawio"])

    # Linux: PyInstaller ignores --icon; the icon is set at runtime via Qt's setWindowIcon.

    pyinstaller_run(args)


if __name__ == "__main__":
    main()
