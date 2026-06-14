# svg-decompose-to-drawio

Convert SVG files into editable [draw.io](https://app.diagrams.net/) diagrams where every supported SVG element becomes an individual, selectable cell instead of a single embedded image.

## Why

Standard SVG-to-draw.io converters often embed the whole file as one opaque image. This tool parses each supported SVG element and maps it to a native draw.io cell so you can select, move, restyle, or delete shapes independently inside draw.io.

## Supported SVG elements

| SVG element | draw.io output |
|---|---|
| `<line>` | Edge (connector, no arrow by default) |
| `<circle>` | Ellipse cell |
| `<ellipse>` | Ellipse cell |
| `<rect>` | Rectangle cell (rounded corner radius computed from `rx`/`ry`) |
| `<text>` / `<tspan>` | Text cell |
| `<polyline>` | Edge with waypoints |
| `<polygon>` | Filled stencil shape |
| `<path>` | Stencil (closed/filled) or curved edge (open/unfilled) |
| `<image>` | draw.io image cell with embedded asset data |
| `<use>` | Resolved from `<defs>`, rendered in place |
| `<symbol>` + `<use>` | Symbol viewBox applied when rendering via `<use width/height>` |
| `<g>` | Native draw.io group cell; children selectable as a group |
| `<a>` | Passes `link=URL` to all child cells |
| nested `<svg>` | Handled with its own `viewBox` transform |

## Supported SVG features

- CSS `<style>` blocks with element, class (`.cls`), ID (`#id`), descendant (`g rect`), and inline `style=""` selectors, with CSS inheritance through `<g>` groups
- `currentColor` in `fill` / `stroke` resolves to the inherited CSS `color` property
- `display:none` and `visibility:hidden` correctly skip elements
- Transforms: `translate`, `scale`, `rotate`, `matrix`, `skewX`, `skewY`
- Root and nested `viewBox` mapping
- `<defs>` + `<use>` reuse
- Linear and radial gradients with `gradientTransform` direction support
- `marker-start` / `marker-end` / `marker-mid` mapped to draw.io arrows and intermediate dots
- `opacity`, `fill-opacity`, `stroke-opacity`
- `stroke-dasharray`, `stroke-dashoffset`, `stroke-linecap`, `stroke-linejoin`
- `fill-rule: evenodd` propagated to stencil shapes
- Font styles: `font-weight`, `font-style`, `font-size`, `text-anchor`, `text-decoration` (underline, line-through)
- `<title>` child element mapped to draw.io tooltip
- `feDropShadow` filter mapped to draw.io shadow style
- Arc commands (`A` / `a`) converted to cubic Bezier curves
- Quadratic and cubic Bezier edges sampled at curve points (not control points)
- Common color formats: hex, `rgb()`, `rgba()`, `none`, `transparent`
- `<image>` with local file paths or `data:` URIs for SVG / PNG / other common image formats

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

## Project structure

```text
main.py                      # CLI entry point
svg_to_drawio/
|-- converter.py             # Orchestration
|-- css.py                   # CSS parsing and inheritance
|-- defs.py                  # <defs> index and <use> resolution
|-- drawio_output.py         # draw.io XML generation
|-- path_utils.py            # Path parsing, arc-to-Bezier, stencil builder
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

## Test fixture

The repository includes `tests/fixtures/test_all_features.svg`, a compact fixture that exercises the main supported SVG features in one file, including `<image>` with local `SVG` and `PNG` assets.

```bash
python main.py tests/fixtures/test_all_features.svg
```

This generates `tests/fixtures/test_all_features.drawio` next to the fixture.

## Transform rendering

| Transform type | draw.io output |
|---|---|
| `translate`, `scale` | Native geometry offset / scaling |
| `rotate(theta)` | Native `rotation=theta` style around the shape center |
| `skewX`, `skewY`, or any matrix with shear | Stencil with transformed geometry baked in |
| Combined `translate + rotate` | Native rotation style with corrected center position |
| Nested groups | All transforms accumulated before rendering |

Open, unfilled curved paths (`fill="none"` with no closing `Z`) are rendered as draw.io curved edges rather than stencils, because stencils are better suited to closed filled shapes.

## Re-exporting to SVG from draw.io

By default, draw.io renders text labels as HTML and wraps them in `<foreignObject>` blocks when exporting to SVG. Many SVG viewers and tools (Canva, Inkscape, browsers in strict mode) do not support `<foreignObject>`, which causes import errors.

Before exporting to SVG, convert all labels to native SVG text:

1. **Edit → Select All**
2. In the right-hand text panel, click **"Convert labels to SVG"**
3. Then **File → Export as → SVG**

See the [draw.io discussion on foreignObject compatibility](https://github.com/jgraph/drawio/discussions/5165) for more context.

## Limitations

- `<image>` with shear-heavy transforms is approximated by its transformed bounding box because draw.io image cells do not support true skew/shear.
- `<clipPath>` and `<mask>` are ignored.
- Text width is estimated from character count, so long labels may need manual resizing.
- Only `feDropShadow` is supported from `<filter>`; other filter effects (blur, compositing, etc.) are ignored.
- Gradient approximation uses the two endpoint stop colors only; intermediate color stops are dropped.

## License

See [LICENSE](LICENSE).
