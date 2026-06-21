# Interface parity

The CLI, Python API, and desktop app all call the same conversion engine. Given the same
SVG and the same rendering/post-processing options, they produce the same draw.io content.
The interfaces differ only where their workflows naturally differ.

| Capability | CLI | Python API | Desktop app |
|---|---|---|---|
| Single-file and multi-root batch conversion | Positional inputs | `ConversionService.convert(...)` | File/folder queue |
| Recursive folders, overwrite, flatten, max-elements limit | Flags | `ConversionOptions` | Conversion options |
| Parallel conversion | `--workers` | `ConversionService.convert_parallel(...)` | Workers selector |
| Persistent incremental cache | Default; `--no-cache` disables it | `ConversionOptions(use_cache=...)` | Cache checkbox |
| Rendering presets and fine-grained policies | Preset/policy flags | `RenderingOptions` and preset helpers | Rendering settings page |
| Watch mode | `--watch`, optional backend selection | `watch_svg_files(...)` | Watch checkbox with automatic backend selection |
| Structured diagnostics and compatibility matrix | Terminal summary and `--report-json` | `ConversionResult` / `ConversionReport` | Results panel and JSON export |
| Analyze without writing output | `--analyze` | `analyze_file(...)` | Not exposed; the app reports compatibility after conversion |
| CI quality gates | Quality-gate flags | `evaluate_quality_gates(...)` | Not exposed; the app presents the same data interactively |
| Merge as pages or a tile grid | `--merge` | `merge_files(...)` / `ConversionService.merge(...)` | Merge & extras section |
| Cooperative cancellation | Ctrl+C / process interruption | `CancellationToken` on service operations | Cancel button, including merge and watch |
| Notes legend and page background | `--legend`, `--background-color` | `PostProcessOptions` | Merge & extras section |
| XML returned without a file | `--stdout` | `convert_to_string(...)` and in-memory APIs | Not applicable |
| Before/after preview and clickable compatibility zones | Not applicable | Report annotations are available programmatically | Preview page |
| Copy an equivalent CLI command | Not applicable | Not applicable | Copy CLI Command |

## Watch sessions

Watch mode preserves the same rendering and post-processing options as a normal conversion.
In the CLI, `--report-json` and quality gates collect every processed report and are finalized
when the watch session is stopped with Ctrl+C. The desktop app keeps the same session history
available for report export and preview selection.

## Intentional differences

The desktop app does not duplicate automation-only controls such as `--stdout` or CI exit-code
gates. Conversely, the CLI and API do not attempt to reproduce the desktop's interactive
preview. These are interface choices rather than engine capability gaps.
