# Advanced rendering

The engine exposes a small set of rendering policies shared by the CLI, Python API, and desktop app, through [`RenderingOptions`](api-reference.md#svg_to_drawio.RenderingOptions).

If you want the shortest path to those choices:

- Desktop app: pick `Balanced`, `Best editability`, or `Best visual fidelity`
- CLI: use `--rendering-preset balanced|editability|fidelity`
- Python API: use [`rendering_preset_options(...)`](api-reference.md#svg_to_drawio.rendering_preset_options)

- `gradient_policy="auto"` keeps the default behavior: use native multi-stop approximation when supported, otherwise fall back to embedded SVG.
- `gradient_policy="prefer-native"` keeps output editable even for unsupported multi-stop gradients by reducing them to draw.io's native two-color gradients when needed.
- `gradient_policy="prefer-fallback"` always preserves multi-stop gradients through embedded SVG fallback.
- `filter_policy="auto"` keeps the default behavior: native shadows stay native, some glow or simple offset filters may be approximated natively, and harder filters fall back.
- `filter_policy="prefer-native"` ignores unsupported filters instead of falling back so the surrounding shapes stay editable, while still keeping supported native approximations.
- `filter_policy="force-fallback"` always preserves filters through embedded SVG fallback.
- `text_metrics_policy="auto"` uses Qt text shaping when `PySide6` is available, then falls back to Pillow or Tk font metrics, and finally to the built-in heuristic.
- `text_metrics_policy="system"` explicitly prefers real font metrics over the heuristic.
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
