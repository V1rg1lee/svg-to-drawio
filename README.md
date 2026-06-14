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

Python 3.8+ with no external dependencies.

## Usage

Single file:

```bash
python main.py path/to/diagram.svg
```

Entire folder:

```bash
python main.py path/to/folder/
```

Each SVG produces a `.drawio` file next to it with the same base name.

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
|-- converter.py             # Conversion orchestration
|-- css.py                   # CSS parsing, selector matching, inheritance
|-- defs.py                  # <defs> index and <use> resolution
|-- drawio_output.py         # draw.io XML generation
|-- path_utils.py            # Path parsing, bbox, arc-to-Bezier, stencil builder
|-- styles.py                # Visual property extraction
|-- transforms.py            # 2D affine transforms + viewBox mapping
|-- utils.py                 # Shared parsing helpers
`-- elements/
    |-- shapes.py            # line, circle, ellipse, rect
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
- `<clipPath>` and `<mask>` are ignored.
- Text width is estimated from character count, so long labels may need manual resizing.
- Only `feDropShadow` is supported from `<filter>`; other filter effects are ignored.
- Gradient approximation uses the two endpoint stop colors only; intermediate stops are dropped.
- `stop-opacity` is approximated by blending stop colors against white before export.

## License

See [LICENSE](LICENSE).
