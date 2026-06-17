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

Features: drag-and-drop, multi-root queues, live progress, cooperative cancellation, one-click output folder, live watch mode, persistent preferences, advanced rendering controls, and JSON report export.

**Download release artifacts** from the [Releases page](https://github.com/V1rg1lee/svg-to-drawio/releases):

- Windows: `Setup.exe` installer plus a plain `.zip` with executable for advanced users
- Linux: portable `.AppImage` plus a plain `.tar.gz` with executable for advanced users
- macOS: `.zip` archive of the app bundle

The Windows installer upgrades an existing installed version automatically by uninstalling it first, then installing the new release.

Or run from source:

```bash
pip install -r requirements-desktop.txt
python desktop_app.py
```

Build the base standalone bundle (Windows / Linux / macOS):

```bash
python build_desktop.py        # produces dist/desktop/svg-to-drawio.exe (Windows), svg-to-drawio (Linux), svg-to-drawio.app (macOS)
```

Extra packaging layers are built on top of that base bundle:

- Windows installer: `packaging/windows/build_installer.ps1`
- Linux portable AppImage: `packaging/linux/build_appimage.sh`
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

An AppImage is not a system installer like `Setup.exe` on Windows.
It is a portable Linux application bundle that you can usually download, mark as executable, and run directly.

Build the base executable first, then package it with `appimagetool`:

```bash
python -m pip install -r requirements-desktop.txt
python build_desktop.py
curl -L \
  -o appimagetool-x86_64.AppImage \
  https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage packaging/linux/AppRun packaging/linux/build_appimage.sh
VERSION="$(python -c 'from svg_to_drawio import __version__; print(__version__)')"
./packaging/linux/build_appimage.sh \
  dist/desktop/svg-to-drawio \
  "$VERSION" \
  ./appimagetool-x86_64.AppImage \
  "dist/release/svg-to-drawio-${VERSION}-linux-x86_64.AppImage"
```

In GitHub Actions, `appimagetool` is downloaded automatically by the workflow.
For a local Linux build, you need to download it yourself first as shown above.

This produces:

- `dist/release/svg-to-drawio-<version>-linux-x86_64.AppImage`

Typical end-user usage after downloading the AppImage from a release:

```bash
chmod +x svg-to-drawio-<version>-linux-x86_64.AppImage
./svg-to-drawio-<version>-linux-x86_64.AppImage
```

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
| `--analyze` | Inspect SVG compatibility and diagnostics without writing `.drawio` output |
| `--report-json PATH` | Write a structured JSON report with diagnostics, fallbacks, and compatibility scores |
| `--no-cache` | Disable the persistent cache for unchanged inputs |
| `--max-elements N` | Warn and truncate output after N drawable elements |
| `--gradient-policy MODE` | `auto`, `prefer-native`, or `prefer-fallback` for multi-stop gradients |
| `--filter-policy MODE` | `auto`, `prefer-native`, or `force-fallback` for SVG filters |
| `--text-metrics-policy MODE` | `auto`, `system`, or `heuristic` for text sizing |

**Examples:**

```bash
# Write output to a separate folder
python main.py src/icons/ --recursive --output-dir dist/diagrams --overwrite

# Watch a folder and reconvert on every save
python main.py src/ --watch --overwrite

# Analyze a file and emit a JSON report without generating a .drawio file
python main.py diagram.svg --analyze --report-json report.json

# Prefer editable native output over exact SVG filters and complex gradients
python main.py diagram.svg --filter-policy prefer-native --gradient-policy prefer-native

# Pipe draw.io XML directly into another tool
python main.py diagram.svg --stdout > diagram.drawio

# Flatten all groups into a single layer
python main.py diagram.svg --flatten --overwrite
```

## Python API

```python
from svg_to_drawio import RenderingOptions, convert_file, convert_to_string

# Write to disk - returns the output path
out = convert_file("diagram.svg")

# Return XML as a string (no file written)
xml = convert_to_string(
    "diagram.svg",
    rendering_options=RenderingOptions(
        gradient_policy="prefer-native",
        filter_policy="prefer-native",
        text_metrics_policy="heuristic",
    ),
)
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

For one-off diagnostics without writing output files:

```python
from svg_to_drawio import analyze_file

report = analyze_file("diagram.svg")
print(report.compatibility_score)
for issue in report.issues:
    print(issue.message)
```

## Advanced rendering

The engine now exposes a small set of rendering policies that can be shared across the CLI, Python API, and desktop app:

- `gradient_policy="auto"` keeps the current default behaviour: use native multi-stop approximation when supported, otherwise fall back to embedded SVG.
- `gradient_policy="prefer-native"` keeps output editable even for unsupported multi-stop gradients by reducing them to draw.io's native two-colour gradients when needed.
- `gradient_policy="prefer-fallback"` always preserves multi-stop gradients through embedded SVG fallback.
- `filter_policy="auto"` keeps the current default behaviour: native `feDropShadow` when supported, SVG fallback for unsupported filters.
- `filter_policy="prefer-native"` ignores unsupported filters instead of falling back, so the surrounding shapes stay editable.
- `filter_policy="force-fallback"` always preserves filters through embedded SVG fallback.
- `text_metrics_policy="auto"` uses platform metrics when available and a tuned heuristic otherwise.
- `text_metrics_policy="system"` explicitly prefers platform font metrics.
- `text_metrics_policy="heuristic"` keeps text sizing deterministic without consulting the system font backend.

## What gets converted

| SVG element | draw.io output |
|---|---|
| `<rect>` | Rectangle cell (rounded corners from `rx` / `ry`) |
| `<circle>` / `<ellipse>` | Ellipse cell |
| `<line>` | Edge (no arrow by default) |
| `<polyline>` | Edge with waypoints |
| `<polygon>` | Filled stencil shape |
| `<path>` | Stencil; open unfilled paths with markers become edges; multi-stop linear gradients approximated natively |
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
- Multi-stop linear gradients on `<rect>`, `<circle>`, `<ellipse>`, and `<path>` approximated natively as stacked two-colour gradient bands (no SVG fallback); each band carries an exact draw.io two-colour gradient aligned to its stop interval
- Multi-stop radial gradients on `<rect>`, `<circle>`, `<ellipse>` approximated as adaptive concentric rings (ring count scales with shape radius, up to 96 rings)
- `marker-start`, `marker-end`, `marker-mid`
- `opacity`, `fill-opacity`, `stroke-opacity`
- `stroke-dasharray`, `stroke-linecap`, `stroke-linejoin`, `fill-rule: evenodd`
- Text: `font-weight`, `font-style`, `font-size`, `font-family`, `text-anchor`, `text-decoration`
- Embedded SVG fallback for `clip-path`, `mask`, pattern fills, and unsupported filters so those fragments keep their appearance
- Structured diagnostics and compatibility scoring for CLI, automation, and the desktop app
- `<title>` → draw.io tooltip; `feDropShadow` → draw.io shadow style
- Color formats: hex (`#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa`), `rgb()`, `rgba()`, `hsl()`, `hsla()`, `none`, `transparent`
- Local `<image>` paths and `data:` URIs (SVG, PNG); assets are embedded into the output

## Limitations

- `<clipPath>`, `<mask>`, pattern fills, and unsupported filters fall back to embedded SVG images for visual fidelity, so those fragments are less editable than native shapes.
- Only `feDropShadow` is mapped to native draw.io shadow styles; other filter effects use the embedded SVG fallback path when possible.
- Multi-stop **radial** gradients on `<path>` elements fall back to embedded SVG; draw.io's radial gradient always fills the entire cell bounding box so disk-clipping to an arbitrary path outline is not feasible natively. Radial gradients on `<rect>`, `<circle>`, and `<ellipse>` are approximated with concentric rings.
- Two-stop gradients (one interval) are mapped directly to draw.io's native gradient properties. `stop-opacity` is blended against white for all gradient types.
- Multi-stop gradients combined with a CSS `filter` or a shear transform fall back to embedded SVG because the filter or skew effect itself requires SVG.
- The advanced rendering policies can intentionally trade exact fidelity for editability by keeping native shapes and simplifying unsupported gradients or filters.
- Text uses platform font metrics when they are available, with a tuned heuristic fallback in headless environments.
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

The checked-in fixture regression snapshot is intentionally generated with
`text_metrics_policy="heuristic"` so it stays stable across Windows, Linux,
and CI runners even when system font backends differ.

To regenerate the versioned fixture baseline deterministically:

```bash
python -m tests.regenerate_fixtures
```

**Lint & type-check:**

```bash
python -m ruff check main.py svg_to_drawio svg_to_drawio_desktop tests
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
├── polygon_clip.py          # Sutherland–Hodgman polygon clipper for gradient band approximation
├── styles.py                # Visual property extraction
├── style_builder.py         # draw.io style-string builder
├── transforms.py            # 2D affine transforms + viewBox mapping
├── utils.py                 # Shared parsing helpers
└── elements/
    ├── gradient_approx.py   # Multi-stop gradient native approximation (bands + radial rings)
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
