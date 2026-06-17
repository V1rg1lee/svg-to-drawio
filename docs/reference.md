# Compatibility reference

## Capability keys

The compatibility matrix, the desktop app's compatibility panel, and the CLI's `--require-native` flag all group features into the same capability families, available programmatically via [`all_capabilities`](api-reference.md#svg_to_drawio.all_capabilities) and [`capability_keys`](api-reference.md#svg_to_drawio.capability_keys):

| Key | Covers |
|---|---|
| `shapes` | Rectangles, circles, polygons, and general paths |
| `text` | Text, tspans, anchors, and text measurement |
| `gradients` | Linear, radial, and multi-stop gradients |
| `filters` | Drop shadows, blur, and other SVG filters |
| `clipping` | `<clipPath>` and `<mask>` |
| `patterns` | `<pattern>` fills |
| `markers` | `marker-start` / `marker-mid` / `marker-end` |
| `images` | Embedded or local raster/SVG image assets |
| `references` | `<use>`, `<symbol>`, and nested `<svg>` |

## What gets converted

| SVG element | draw.io output |
|---|---|
| `<rect>` | Rectangle cell (rounded corners from `rx` / `ry`) |
| `<circle>` / `<ellipse>` | Ellipse cell |
| `<line>` | Edge (no arrow by default) |
| `<polyline>` | Edge with waypoints |
| `<polygon>` | Filled stencil shape |
| `<path>` | Stencil; open unfilled paths with markers become edges; multi-stop linear gradients can be approximated natively |
| `<text>` / `<tspan>` | Text cell |
| `<image>` | Image cell with embedded asset data |
| `<g>` | Native draw.io group cell |
| Inkscape layers (`<g inkscape:groupmode="layer">`) | draw.io layer cell |
| `<a>` | Passes `link=URL` to child cells |
| `<use>` / `<symbol>` | Resolved from `<defs>` and rendered in place |
| nested `<svg>` | Handled with its own `viewBox` transform |

## Supported CSS and SVG features

- CSS `<style>` blocks: element, class (`.cls`), ID (`#id`), descendant (`A B`), child (`A > B`), multi-class (`.a.b`), and attribute selectors
- CSS inheritance through `<g>` groups and custom properties (`var(--name, fallback)`)
- `currentColor`, `display:none`, and `visibility:hidden`
- Transforms: `translate`, `scale`, `rotate`, `matrix`, `skewX`, `skewY`
- `viewBox` mapping with `preserveAspectRatio` on both root and nested SVGs
- `<defs>` + `<use>` reuse
- Linear and radial gradients with `gradientTransform` and `xlink:href` inheritance
- Multi-stop linear gradients on `<rect>`, `<circle>`, `<ellipse>`, and `<path>` approximated natively as stacked two-color gradient bands
- Multi-stop radial gradients on `<rect>`, `<circle>`, and `<ellipse>` approximated as adaptive concentric rings
- `marker-start`, `marker-end`, and `marker-mid` with closest draw.io arrow matching, plus simple custom endpoint marker shapes
- `opacity`, `fill-opacity`, `stroke-opacity`
- `stroke-dasharray`, `stroke-linecap`, `stroke-linejoin`, `fill-rule: evenodd`
- Text: `font-weight`, `font-style`, `font-size`, `font-family`, `text-anchor`, `text-decoration`, approximate `dominant-baseline`
- `<textPath>` flattened into regular editable text near the original anchor point, with a compatibility warning
- Simple `clip-path` / `mask` rewrites for some solid-filled cases; otherwise embedded SVG fallback keeps the appearance
- Structured diagnostics, compatibility scoring, and a user-facing compatibility matrix for CLI, automation, and the desktop app
- `<title>` -> draw.io tooltip; `feDropShadow` -> draw.io shadow style
- Color formats: hex (`#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa`), `rgb()`, `rgba()`, `hsl()`, `hsla()`, `none`, `transparent`
- Local `<image>` paths and `data:` URIs (SVG, PNG); assets are embedded into the output

## Limitations

- Some very simple solid-filled `clipPath` and `mask` cases can stay editable, but most advanced clips, masks, pattern fills, and unsupported filters still fall back to embedded SVG images for visual fidelity.
- Only `feDropShadow` is mapped to native draw.io shadow styles; other filter effects use embedded SVG fallback when possible.
- Multi-stop radial gradients on `<path>` elements fall back to embedded SVG because draw.io's radial gradient always fills the whole cell bounding box.
- Two-stop gradients are mapped directly to draw.io's native gradient properties. `stop-opacity` is blended against white for all gradient types.
- Multi-stop gradients combined with a CSS `filter` or a shear transform fall back to embedded SVG because the filter or skew effect itself requires SVG.
- The advanced rendering policies can intentionally trade exact fidelity for editability by keeping native shapes and simplifying unsupported gradients or filters.
- Text uses platform font metrics when available, with a tuned heuristic fallback in headless environments.
- `letter-spacing` is reported when encountered, but draw.io text does not preserve it natively.
- `<image>` with shear-heavy transforms is approximated by its bounding box because draw.io image cells do not support true skew.
- Local `<image>` paths are resolved relative to the SVG file being converted and must stay inside the source SVG's folder tree; the resulting asset is embedded into the `.drawio` output so it stays self-contained.
- Raster `<image>` assets are wrapped in a tiny SVG before embedding because draw.io handles embedded SVGs more reliably than raw PNGs.

## Transform rendering

| Transform | draw.io output |
|---|---|
| `translate`, `scale` | Native geometry offset / scaling |
| `rotate(theta)` | Native `rotation=...` style around the shape center |
| `skewX`, `skewY`, or any matrix with shear | Stencil with baked-in geometry |
| Combined `translate + rotate` | Native rotation with corrected center |
| Nested groups | All transforms accumulated before rendering |

Open, unfilled paths with SVG markers become draw.io edges so arrowheads stay editable.

## Re-exporting to SVG from draw.io

draw.io wraps text labels in `<foreignObject>` when exporting SVG, which many tools do not support. Before exporting:

1. **Edit -> Select All**
2. In the right-hand panel, click **Convert labels to SVG**
3. **File -> Export as -> SVG**
