# svg-decompose-to-drawio

Convert SVG files into editable [draw.io](https://app.diagrams.net/) diagrams where **every SVG element becomes an individual, selectable cell**, not a single embedded image.

## Why

Standard SVG-to-draw.io converters embed the whole file as an opaque base64 image. This tool parses each SVG element and maps it to a native draw.io cell, so you can select, move, restyle, or delete any shape independently inside draw.io.

## Supported SVG elements

| SVG element | draw.io output |
|---|---|
| `<line>` | Edge (connector without arrow) |
| `<circle>` | Ellipse cell |
| `<ellipse>` | Ellipse cell |
| `<rect>` | Rectangle cell (rounded if `rx` is set) |
| `<text>` / `<tspan>` | Text cell |
| `<polyline>` | Edge with waypoints |
| `<polygon>` | Filled stencil shape |
| `<path>` | Custom stencil shape (M/L/H/V/C/c/S/Q/A/Z) |
| `<g>` | Transparent group — children are flattened with accumulated transforms |

Stroke color, fill color, stroke width, opacity, font size, and text alignment are all preserved.

## Requirements

Python 3.8+ — no external dependencies (standard library only).

## Usage

**Single file:**
```bash
python svg_decompose_to_drawio.py path/to/diagram.svg
```

**Entire folder:**
```bash
python svg_decompose_to_drawio.py path/to/folder/
```

Each SVG produces a `.drawio` file next to it with the same base name.

## Example

The `gossip/` folder contains a sample SVG representing a GossipSub overlay network (nodes and mesh edges). Running the script on it:

```bash
python svg_decompose_to_drawio.py gossip/gossipsub_overlay.svg
```

Produces `gossip/gossipsub_overlay.drawio` with 35 independent cells:
- 20 edge cells (white mesh lines + orange source edges)
- 9 ellipse cells (network nodes)
- 4 edge cells (legend lines)
- 2 text cells (legend labels)

Open the `.drawio` file in draw.io and each element is immediately selectable and editable.

## Limitations

- `<use>`, `<image>`, `<clipPath>`, and `<mask>` elements are ignored.
- Arc commands (`A`/`a`) in paths are approximated as straight lines to the end point.
- Text width is estimated from character count; long labels may need manual resizing.
- Rotated `<rect>` or `<ellipse>` elements (via `transform="rotate(...)"`) are placed at their transformed bounding box but not visually rotated inside draw.io.

## License

See [LICENSE](LICENSE).
