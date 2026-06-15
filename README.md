# svg-to-drawio

Convert SVG files into editable [draw.io](https://app.diagrams.net/) diagrams where each SVG element becomes an individual, selectable draw.io cell - not a single embedded image.

## Quick start

**Requirements:** Python 3.11+, no external dependencies.

```bash
# Convert one file
python main.py diagram.svg

# Convert a folder (recursive, overwrite existing outputs)
python main.py path/to/folder/ --recursive --overwrite
```

The output is written next to the source file by default (`diagram.svg` → `diagram.drawio`).

## Desktop app

A desktop front-end shares the same conversion engine as the CLI.

Features: drag-and-drop, multi-root queues, live progress, cooperative cancellation, one-click output folder.

**Download release artifacts** from the [Releases page](https://github.com/V1rg1lee/svg-to-drawio/releases):

- Windows: `Setup.exe` installer plus a plain `.zip` for advanced users
- Linux: `.AppImage` plus a plain `.tar.gz` for advanced users
- macOS: `.zip` archive of the app bundle

The Windows installer upgrades an existing installed version automatically by uninstalling it first, then installing the new release.

Or run from source:

```bash
pip install -r requirements-desktop.txt
python desktop_app.py
```

Build the base standalone bundle (Windows / Linux / macOS):

```bash
python build_desktop.py        # produces dist/desktop/svg-to-drawio/
```

Extra packaging layers are built on top of that base bundle:

- Windows installer: `packaging/windows/build_installer.ps1`
- Linux AppImage: `packaging/linux/build_appimage.sh`
- macOS: archive only for now

### Manual packaging

#### Windows installer

The Windows installer is built with Inno Setup.

Install Inno Setup first, for example with:

```powershell
winget install JRSoftware.InnoSetup
```

Then build the base executable and wrap it into a `Setup.exe`:

```powershell
env\Scripts\python.exe -m pip install -r requirements-desktop.txt
env\Scripts\python.exe build_desktop.py
$version = env\Scripts\python.exe -c "from svg_to_drawio import __version__; print(__version__)"
.\packaging\windows\build_installer.ps1 -Version $version -InputExe "dist\desktop\svg-to-drawio.exe" -OutputDir "dist\release"
```

This produces:

- `dist\release\svg-to-drawio-<version>-setup.exe`

The installer upgrades an existing installed version automatically by uninstalling it first, then installing the new version.

#### Linux AppImage

Build the base executable first, then package it with `appimagetool`:

```bash
python -m pip install -r requirements-desktop.txt
python build_desktop.py
chmod +x appimagetool-x86_64.AppImage packaging/linux/AppRun packaging/linux/build_appimage.sh
VERSION="$(python -c 'from svg_to_drawio import __version__; print(__version__)')"
./packaging/linux/build_appimage.sh \
  dist/desktop/svg-to-drawio \
  "$VERSION" \
  ./appimagetool-x86_64.AppImage \
  "dist/release/svg-to-drawio-${VERSION}-linux-x86_64.AppImage"
```

This produces:

- `dist/release/svg-to-drawio-<version>-linux-x86_64.AppImage`

The plain `.zip` / `.tar.gz` archives remain available for advanced users who prefer to launch the raw bundle directly.

## CLI reference

```
python main.py [INPUT] [OPTIONS]
```

| Option | Description |
|---|---|
| `--output-dir DIR` | Write `.drawio` files into a separate directory |
| `--recursive` | Walk subfolders when the input is a directory |
| `--overwrite` | Replace existing `.drawio` outputs (skip by default) |
| `--stdout` | Write XML to stdout instead of a file (single file only) |
| `--watch` | Re-convert SVG files automatically whenever they change |
| `--flatten` | Dissolve `<g>` groups; emit all shapes at the root level |
| `--max-elements N` | Warn and truncate output after N drawable elements |

**Examples:**

```bash
# Write output to a separate folder
python main.py src/icons/ --recursive --output-dir dist/diagrams --overwrite

# Watch a folder and reconvert on every save
python main.py src/ --watch --overwrite

# Pipe draw.io XML directly into another tool
python main.py diagram.svg --stdout > diagram.drawio

# Flatten all groups into a single layer
python main.py diagram.svg --flatten --overwrite
```

## Python API

```python
from svg_to_drawio import convert_file, convert_to_string

# Write to disk - returns the output path
out = convert_file("diagram.svg")

# Return XML as a string (no file written)
xml = convert_to_string("diagram.svg")
```

For batch conversions with progress reporting and cancellation:

```python
from svg_to_drawio import ConversionService, ConversionOptions

service = ConversionService()
summary = service.convert(
    ["folder/", "other.svg"],
    ConversionOptions(output_dir="out/", recursive=True, overwrite=True),
    reporter=lambda event: print(event.message),
)
print(summary.to_status_line())
```

## What gets converted

| SVG element | draw.io output |
|---|---|
| `<rect>` | Rectangle cell (rounded corners from `rx` / `ry`) |
| `<circle>` / `<ellipse>` | Ellipse cell |
| `<line>` | Edge (no arrow by default) |
| `<polyline>` | Edge with waypoints |
| `<polygon>` | Filled stencil shape |
| `<path>` | Stencil; open unfilled paths with markers become edges |
| `<text>` / `<tspan>` | Text cell |
| `<image>` | Image cell with embedded asset data |
| `<g>` | Native draw.io group cell |
| Inkscape layers (`<g inkscape:groupmode="layer">`) | draw.io layer cell |
| `<a>` | Passes `link=URL` to child cells |
| `<use>` / `<symbol>` | Resolved from `<defs>` and rendered in place |
| nested `<svg>` | Handled with its own `viewBox` transform |

## Supported CSS & SVG features

- CSS `<style>` blocks: element, class (`.cls`), ID (`#id`), descendant (`A B`), child (`A > B`), multi-class (`.a.b`), attribute selectors
- CSS inheritance through `<g>` groups and custom properties (`var(--name, fallback)`)
- `currentColor`, `display:none`, `visibility:hidden`
- Transforms: `translate`, `scale`, `rotate`, `matrix`, `skewX`, `skewY`
- `viewBox` mapping with `preserveAspectRatio` (root and nested)
- `<defs>` + `<use>` reuse
- Linear and radial gradients with `gradientTransform` and `xlink:href` inheritance
- `marker-start`, `marker-end`, `marker-mid`
- `opacity`, `fill-opacity`, `stroke-opacity`
- `stroke-dasharray`, `stroke-linecap`, `stroke-linejoin`, `fill-rule: evenodd`
- Text: `font-weight`, `font-style`, `font-size`, `font-family`, `text-anchor`, `text-decoration`
- `<title>` → draw.io tooltip; `feDropShadow` → draw.io shadow style
- Color formats: hex (`#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa`), `rgb()`, `rgba()`, `hsl()`, `hsla()`, `none`, `transparent`
- Local `<image>` paths and `data:` URIs (SVG, PNG); assets are embedded into the output

## Limitations

- `<clipPath>` and `<mask>` are ignored.
- Only `feDropShadow` is supported from `<filter>`; other filter effects are ignored.
- Gradient approximation uses the two endpoint stop colors only; intermediate stops are dropped. `stop-opacity` is blended against white.
- Text width is estimated from character count - long labels may need manual resizing.
- `<image>` with shear-heavy transforms is approximated by its bounding box; draw.io image cells do not support true skew.
- Local `<image>` paths are restricted to files inside the source SVG's folder tree.
- Raster `<image>` assets are wrapped in a tiny SVG before embedding (draw.io handles embedded SVGs more reliably than raw PNGs).

## Transform rendering

| Transform | draw.io output |
|---|---|
| `translate`, `scale` | Native geometry offset / scaling |
| `rotate(θ)` | Native `rotation=θ` style around the shape center |
| `skewX`, `skewY`, or any matrix with shear | Stencil with baked-in geometry |
| Combined `translate + rotate` | Native rotation with corrected center |
| Nested groups | All transforms accumulated before rendering |

Open, unfilled paths with SVG markers become draw.io edges so arrowheads stay editable.

## Re-exporting to SVG from draw.io

draw.io wraps text labels in `<foreignObject>` when exporting SVG, which many tools don't support. Before exporting:

1. **Edit → Select All**
2. In the right-hand panel, click **"Convert labels to SVG"**
3. **File → Export as → SVG**

## Image resolution

Local `<image>` paths are resolved relative to the SVG file being converted, then embedded in the `.drawio` output so it stays self-contained.

## Development

**Run tests:**

```bash
python -m unittest discover -s tests -v
```

**Lint & type-check:**

```bash
python -m ruff check main.py svg_to_drawio tests
python -m mypy
```

**Install dev tooling and Git hooks:**

```bash
pip install -r requirements-dev.txt
python -m pre_commit install --hook-type pre-commit --hook-type pre-push
python -m pre_commit run --all-files
```

Pre-commit runs ruff, mypy, and basic hygiene checks on every commit. Tests run on every push. GitHub Actions mirrors both locally.

## Project structure

```
main.py                      # CLI entry point
desktop_app.py               # Desktop application
build_desktop.py             # PyInstaller bundle builder
packaging/                   # Installer and AppImage packaging assets
svg_to_drawio/
├── conversion_service.py    # Shared batch service (CLI + desktop)
├── converter.py             # Conversion orchestration
├── css.py                   # CSS parsing, selector matching, cascade
├── defs.py                  # <defs> index, gradient & marker resolution
├── drawio_model.py          # Cell model + XML serialization
├── drawio_output.py         # draw.io document wrapper
├── emitter_context.py       # Per-conversion state for emitters
├── cell_factory.py          # Cell construction helpers
├── element_geometry.py      # Transformed bounds
├── path_parser.py           # SVG path tokenization and command parsing
├── path_bounds.py           # Tight bounding boxes for path commands
├── path_stencil.py          # Path → stencil serialization
├── path_utils.py            # Path helper facade
├── styles.py                # Visual property extraction
├── style_builder.py         # draw.io style-string builder
├── transforms.py            # 2D affine transforms + viewBox mapping
├── utils.py                 # Shared parsing helpers
└── elements/
    ├── shapes.py            # line, circle, ellipse, rect
    ├── text.py              # text / tspan
    ├── poly.py              # polyline, polygon
    ├── path.py              # path
    ├── image.py             # image
    ├── shape_paths.py       # Primitive path generation
    ├── shape_support.py     # Shared stencil helpers
    └── style_support.py     # Shared emitter-side style helpers
svg_to_drawio_desktop/
├── app.py                   # PySide6 window
├── widgets.py               # Drag-and-drop widgets
└── worker.py                # Background conversion thread
tests/
├── unit/                    # Rendering, styles, transforms, structure, fuzz
└── integration/             # CLI and end-to-end flows
```

## License

See [LICENSE](LICENSE).
