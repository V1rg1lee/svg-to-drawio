# svg-to-drawio

Turn any SVG into a real, editable [draw.io](https://app.diagrams.net/) diagram. Every shape, line, and text label becomes its own selectable cell - not a single flattened picture pasted onto the canvas.

<p align="center">
  <img src="assets/svg-to-drawio-demo.gif" alt="svg-to-drawio demo" width="1000">
</p>

- **Truly editable output** - rectangles, circles, paths, text, and groups all stay as native, movable draw.io cells.
- **One engine, three ways in** - the CLI, the Python API, and the desktop app all share the exact same conversion logic, so results are identical everywhere.
- **Shared rendering controls everywhere** - the same presets and advanced rendering policies are available across the desktop app, CLI, and Python API.
- **Smart fallbacks, not silent failures** - gradients, filters, masks, and clip-paths render natively whenever draw.io supports them, and fall back to a faithful embedded SVG image when it can't, instead of dropping detail.
- **Built for batches** - convert a single icon or an entire folder tree recursively, with watch mode, incremental caching, and structured diagnostics.

## Where to go next

- [Quick start](quickstart.md) - install the package and convert your first file.
- [Desktop downloads](release-downloads.md) - choose the right desktop package and verify release assets.
- [CLI reference](cli.md) - every command-line option, with examples.
- [Python API](python-api.md) - use the conversion engine directly from your own code.
- [Advanced rendering](advanced-rendering.md) - trade fidelity against editability for gradients, filters, and text.
- [Compatibility reference](reference.md) - exactly what SVG/CSS features are supported, approximated, or fall back to an embedded image.
- [API reference](api-reference.md) - auto-generated reference for every public class and function.

## Project links

- [Source code](https://github.com/V1rg1lee/svg-to-drawio)
- [Releases](https://github.com/V1rg1lee/svg-to-drawio/releases) (desktop app installers for Windows, Linux, macOS)
- [Issue tracker](https://github.com/V1rg1lee/svg-to-drawio/issues)
