# Advanced rendering

The engine exposes a small set of rendering policies shared by the CLI, Python API, and desktop app, through [`RenderingOptions`](api-reference.md#svg_to_drawio.RenderingOptions).

- `gradient_policy="auto"` keeps the default behavior: use native multi-stop approximation when supported, otherwise fall back to embedded SVG.
- `gradient_policy="prefer-native"` keeps output editable even for unsupported multi-stop gradients by reducing them to draw.io's native two-color gradients when needed.
- `gradient_policy="prefer-fallback"` always preserves multi-stop gradients through embedded SVG fallback.
- `filter_policy="auto"` keeps the default behavior: native `feDropShadow` when supported, SVG fallback for unsupported filters.
- `filter_policy="prefer-native"` ignores unsupported filters instead of falling back so the surrounding shapes stay editable.
- `filter_policy="force-fallback"` always preserves filters through embedded SVG fallback.
- `text_metrics_policy="auto"` uses platform text metrics when available and a tuned heuristic otherwise.
- `text_metrics_policy="system"` explicitly prefers platform font metrics.
- `text_metrics_policy="heuristic"` keeps text sizing deterministic without consulting the system font backend.

These policies intentionally let you trade exact visual fidelity for editability. See the [compatibility reference](reference.md) for the full list of supported features and known limitations.

## Presets

The desktop app exposes three beginner-friendly presets built on top of those policies, also available programmatically via [`rendering_preset_options`](api-reference.md#svg_to_drawio.rendering_preset_options):

| Preset | `gradient_policy` | `filter_policy` | `text_metrics_policy` |
|---|---|---|---|
| `balanced` | `auto` | `auto` | `auto` |
| `editability` ("Best editability") | `prefer-native` | `prefer-native` | `heuristic` |
| `fidelity` ("Best visual fidelity") | `prefer-fallback` | `force-fallback` | `system` |

```python
from svg_to_drawio import detect_rendering_preset, rendering_preset_options

options = rendering_preset_options("editability")
detect_rendering_preset(options)  # "editability", or None for a custom mix
```
