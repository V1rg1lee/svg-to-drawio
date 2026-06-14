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
| `<rect>` | Rectangle cell (rounded if `rx` or `ry` is set) |
| `<text>` / `<tspan>` | Text cell |
| `<polyline>` | Edge with waypoints |
| `<polygon>` | Filled stencil shape |
| `<path>` | Custom stencil shape (all commands supported) |
| `<use>` | Resolved from `<defs>`, rendered in place |
| `<g>` | Transparent group with accumulated transforms |
| nested `<svg>` | Handled with its own `viewBox` transform |

## Supported SVG features

- CSS `<style>` blocks with element selectors, class selectors, inline `style=""`, and inheritance through `<g>` groups
- Transforms: `translate`, `scale`, `rotate`, `matrix`, `skewX`, `skewY`
- Root and nested `viewBox` mapping
- `<defs>` + `<use>` reuse
- Linear and radial gradients mapped to draw.io gradients
- `marker-start` / `marker-end` mapped to draw.io arrows
- Opacity attributes such as `opacity`, `fill-opacity`, and `stroke-opacity`
- Stroke styles such as `stroke-dasharray`, `stroke-linecap`, `stroke-linejoin`
- Font styles such as `font-weight`, `font-style`, `font-size`, `text-anchor`
- Arc commands (`A` / `a`) converted to cubic Bezier curves
- Common color formats including hex, `rgb()`, `rgba()`, `none`, and `transparent`

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
    `-- path.py              # path
```

## Test fixture

The repository includes `tests/fixtures/test_all_features.svg`, a compact fixture that exercises the main supported SVG features in one file.

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

## Limitations

- `<image>` elements are currently ignored.
- `<clipPath>` and `<mask>` are ignored.
- Text width is estimated from character count, so long labels may need manual resizing.
- `<filter>` effects such as blur or shadow are not supported.
- Gradient approximation currently uses the two endpoint stop colors only.

## License

See [LICENSE](LICENSE).
