# svg-decompose-to-drawio

Convert SVG files into editable [draw.io](https://app.diagrams.net/) diagrams where each supported SVG element becomes an individual, selectable draw.io cell instead of a single embedded image.

## Why

Typical SVG-to-draw.io flows import the whole SVG as one opaque image. This project takes the opposite approach: it parses supported SVG elements and maps them to native draw.io cells so you can move, restyle, regroup, or delete them directly inside draw.io.

## Supported SVG Elements

| SVG element | draw.io output |
|---|---|
| `<line>` | Edge (connector, no arrow by default) |
| `<circle>` | Ellipse cell |
| `<ellipse>` | Ellipse cell |
| `<rect>` | Rectangle cell, with rounded corners from `rx` / `ry` |
| `<text>` / `<tspan>` | Text cell |
| `<polyline>` | Edge with waypoints |
| `<polygon>` | Filled stencil shape |
| `<path>` | Stencil by default; open unfilled paths with markers become edges |
| `<image>` | Image cell with embedded asset data |
| `<use>` | Resolved from `<defs>` and rendered in place |
| `<symbol>` + `<use>` | Symbol `viewBox` applied when rendering through `<use width/height>` |
| `<g>` | Native draw.io group cell |
| `<a>` | Passes `link=URL` to child cells |
| nested `<svg>` | Handled with its own `viewBox` transform |

## Supported SVG Features

- CSS `<style>` blocks with element, class (`.cls`), ID (`#id`), descendant (`A B`), child (`A > B`), multi-class (`.a.b`), and attribute selectors
- CSS inheritance through `<g>` groups
- CSS custom properties with `var(--name, fallback)`
- `currentColor` in `fill` / `stroke`
- `display:none` and `visibility:hidden`
- Transforms: `translate`, `scale`, `rotate`, `matrix`, `skewX`, `skewY`
- Root and nested `viewBox` mapping, including `preserveAspectRatio`
- `<defs>` + `<use>` reuse
- Linear and radial gradients with `gradientTransform`
- `marker-start`, `marker-end`, and `marker-mid`
- `opacity`, `fill-opacity`, `stroke-opacity`
- `stroke-dasharray`, `stroke-linecap`, `stroke-linejoin`
- `fill-rule: evenodd`
- Text styling: `font-weight`, `font-style`, `font-size`, `font-family`, `text-anchor`, `text-decoration`
- `<title>` mapped to draw.io tooltip
- `feDropShadow` mapped to draw.io shadow style
- Arc commands (`A` / `a`) converted to cubic Bezier curves
- Quadratic and cubic Bezier edges sampled on-curve instead of using control points
- Common color formats: hex, `rgb()`, `rgba()`, `hsl()`, `hsla()`, `none`, `transparent`
- `<image>` with local file paths or `data:` URIs for SVG, PNG, and similar formats

## Requirements

Python 3.11+ with no external runtime dependencies.

For development tooling, see `requirements-dev.txt`.

## Usage

Single file:

```bash
python main.py path/to/diagram.svg --overwrite
```

Entire folder:

```bash
python main.py path/to/folder/ --recursive --output-dir converted --overwrite
```

CLI options:

- `--output-dir DIR` writes `.drawio` files into a separate directory
- `--recursive` walks subfolders when the input is a directory
- `--overwrite` replaces existing `.drawio` outputs; otherwise they are skipped

Without `--output-dir`, each SVG still produces a `.drawio` file next to the source file.

## Image Resolution

For `<image>` elements, local asset paths are resolved relative to the SVG file being converted.

Example:

- converting `tests/fixtures/test_all_features.svg`
- with `<image href="image_asset.png" ... />`
- resolves to `tests/fixtures/image_asset.png`

Local images are then embedded into the generated `.drawio` output, so the resulting file stays self-contained.

## Project Structure

```text
main.py                      # CLI entry point
svg_to_drawio/
|-- cell_factory.py          # draw.io cell and geometry construction helpers
|-- converter.py             # Conversion orchestration
|-- css.py                   # CSS parsing, selector matching, inheritance
|-- defs.py                  # <defs> index and <use> resolution
|-- drawio_model.py          # draw.io cell model + XML serialization
|-- drawio_output.py         # draw.io XML generation
|-- element_geometry.py      # Transformed bounds helpers for emitted elements
|-- emitter_context.py       # Typed emitter-facing conversion context
|-- path_utils.py            # Stable facade for path helpers
|-- path_parser.py           # Path tokenization and command parsing
|-- path_bounds.py           # Tight bounding boxes for path commands
|-- path_stencil.py          # Path-to-stencil serialization
|-- styles.py                # Visual property extraction
|-- style_builder.py         # draw.io style-string builder
|-- transforms.py            # 2D affine transforms + viewBox mapping
|-- utils.py                 # Shared parsing helpers
`-- elements/
    |-- shape_paths.py       # Primitive path generation for shapes
    |-- shape_support.py     # Shared stencil helpers for shapes
    |-- shapes.py            # line, circle, ellipse, rect
    |-- style_support.py     # Shared emitter-side style helpers
    |-- text.py              # text / tspan
    |-- poly.py              # polyline, polygon
    |-- path.py              # path
    `-- image.py             # image
```

## Test Fixture

The repository includes `tests/fixtures/test_all_features.svg`, a single fixture that exercises the main supported SVG features, including:

- transforms
- gradients
- markers
- CSS selectors
- grouped elements
- text variants
- embedded local SVG and PNG images

Generate its draw.io counterpart with:

```bash
python main.py tests/fixtures/test_all_features.svg
```

This writes `tests/fixtures/test_all_features.drawio` next to the fixture.

## Tests

Run the automated regression suite with:

```bash
python -m unittest discover -s tests -v
```

Optional static checks:

```bash
python -m ruff check main.py svg_to_drawio tests
python -m mypy
```

## Pre-commit And CI

Install the development tooling and Git hooks with:

```bash
python -m pip install -r requirements-dev.txt
python -m pre_commit install --hook-type pre-commit --hook-type pre-push
```

The repository also includes [`.gitattributes`](.gitattributes) so line endings stay stable between Windows and GitHub.

### What Runs In `pre-commit`

On every local commit, the following hooks run automatically:

- `trailing-whitespace`: removes stray spaces at line ends
- `end-of-file-fixer`: ensures every text file ends with a newline
- `check-yaml`: validates YAML files such as GitHub workflow definitions
- `check-toml`: validates TOML files such as `pyproject.toml`
- `check-merge-conflict`: blocks accidental committed merge markers
- `check-added-large-files`: blocks newly added files larger than 2 MB
- `ruff check --fix`: applies safe lint fixes and import cleanup
- `ruff format`: enforces consistent Python formatting and indentation
- `mypy`: verifies static type consistency across the Python codebase

### What Runs In `pre-push`

Before every push, the test suite runs automatically:

- `python -m unittest discover -s tests -v`

### Manual Commands

Run the full commit-time hook stack:

```bash
python -m pre_commit run --all-files
```

Run the full push-time hook stack:

```bash
python -m pre_commit run --hook-stage pre-push --all-files
```

Run individual hygiene hooks:

```bash
python -m pre_commit run trailing-whitespace --all-files
python -m pre_commit run end-of-file-fixer --all-files
python -m pre_commit run check-yaml --all-files
python -m pre_commit run check-toml --all-files
python -m pre_commit run check-merge-conflict --all-files
python -m pre_commit run check-added-large-files --all-files
```

Run individual Python quality hooks:

```bash
python -m pre_commit run ruff-check --all-files
python -m pre_commit run ruff-format --all-files
python -m pre_commit run mypy --all-files
```

Run the underlying tools directly when that is more convenient:

```bash
python -m ruff check main.py svg_to_drawio tests
python -m ruff format main.py svg_to_drawio tests
python -m mypy
python -m unittest discover -s tests -v
```

### GitHub CI

GitHub Actions runs on every `push`, every `pull_request`, and manual dispatch through [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

The workflow executes:

- the full `pre-commit` stack in the `Quality checks` job
- the regression suite in `Tests (Python 3.11)`
- the regression suite in `Tests (Python 3.14)`

For branch protection, configure these three GitHub status checks as required before merge:

- `Quality checks`
- `Tests (Python 3.11)`
- `Tests (Python 3.14)`

Test layout:

- `tests/unit/` for SVG rendering, styles, transforms, structure, and image handling
- `tests/integration/` for CLI behavior and end-to-end command flows

## Transform Rendering

| Transform type | draw.io output |
|---|---|
| `translate`, `scale` | Native geometry offset / scaling |
| `rotate(theta)` | Native `rotation=theta` style around the shape center |
| `skewX`, `skewY`, or any matrix with shear | Stencil with transformed geometry baked in |
| Combined `translate + rotate` | Native rotation style with corrected center position |
| Nested groups | All transforms accumulated before rendering |

Open, unfilled paths that use SVG markers are rendered as draw.io edges so arrowheads and intermediate markers stay editable. Other paths default to stencils to preserve curve geometry more faithfully.

## Re-exporting to SVG from draw.io

By default, draw.io renders text labels as HTML and wraps them in `<foreignObject>` blocks when exporting to SVG. Many SVG viewers and tools do not support `<foreignObject>`, which can cause import issues.

Before exporting to SVG, convert labels to native SVG text:

1. **Edit -> Select All**
2. In the right-hand text panel, click **"Convert labels to SVG"**
3. Then **File -> Export as -> SVG**

See the [draw.io discussion on foreignObject compatibility](https://github.com/jgraph/drawio/discussions/5165) for more context.

## Limitations

- Raster `<image>` assets are wrapped in a tiny SVG before embedding because draw.io handles embedded SVG image cells more reliably than raw embedded PNG image cells.
- `<image>` with shear-heavy transforms is approximated by its transformed bounding box because draw.io image cells do not support true skew/shear.
- Local `<image>` paths are restricted to files inside the source SVG's folder tree.
- `<clipPath>` and `<mask>` are ignored.
- Text width is estimated from character count, so long labels may need manual resizing.
- Only `feDropShadow` is supported from `<filter>`; other filter effects are ignored.
- Gradient approximation uses the two endpoint stop colors only; intermediate stops are dropped.
- `stop-opacity` is approximated by blending stop colors against white before export.

## License

See [LICENSE](LICENSE).
