# CLI reference

```text
svg-to-drawio [INPUT] [OPTIONS]
```

| Option | Description |
|---|---|
| `--output-dir DIR` | Write `.drawio` files into a separate directory |
| `--recursive` | Walk subfolders when the input is a directory |
| `--overwrite` | Replace existing `.drawio` outputs (skip by default) |
| `--stdout` | Write XML to stdout instead of a file (single file only) |
| `--watch` | Re-convert SVG files automatically whenever they change |
| `--watch-backend MODE` | `auto`, `poll`, or `event` when watch mode is enabled |
| `--flatten` | Dissolve `<g>` groups and emit all shapes at the root level |
| `--analyze` | Inspect compatibility and diagnostics without writing `.drawio` output |
| `--report-json PATH` | Write a structured JSON report with diagnostics, fallbacks, and compatibility data |
| `--no-cache` | Disable the persistent cache for unchanged inputs |
| `--max-elements N` | Warn and truncate output after N drawable elements |
| `--workers N` | Convert files in parallel |
| `--gradient-policy MODE` | `auto`, `prefer-native`, or `prefer-fallback` for multi-stop gradients |
| `--filter-policy MODE` | `auto`, `prefer-native`, or `force-fallback` for SVG filters |
| `--text-metrics-policy MODE` | `auto`, `system`, or `heuristic` for text sizing |
| `--fail-on-warning` | Exit with code 1 if any converted file reports a warning |
| `--fail-on-fallback` | Exit with code 1 if any file uses embedded SVG fallback |
| `--min-score N` | Exit with code 1 if any file scores below N compatibility points |
| `--require-native CAPABILITY...` | Require capability families such as `text`, `gradients`, or `clipping` to stay fully native |

The event-driven `--watch-backend event` mode requires the optional `watchdog` dependency (`pip install "svg-to-drawio[watch]"`); `auto` falls back to polling when it is not installed.

`--fail-on-warning`, `--fail-on-fallback`, `--min-score`, and `--require-native` are quality gates for CI: see [Quality gates](python-api.md#quality-gates-for-ci) for the equivalent Python API.

## Examples

```bash
# Write output to a separate folder
svg-to-drawio src/icons/ --recursive --output-dir dist/diagrams --overwrite

# Watch a folder and reconvert on every save
svg-to-drawio src/ --watch --overwrite

# Force CI to fail if a conversion needed SVG fallback
svg-to-drawio assets/ --recursive --fail-on-fallback --min-score 90

# Analyze a file and emit a JSON report without generating a .drawio file
svg-to-drawio diagram.svg --analyze --report-json report.json

# Prefer editable native output over exact SVG filters and complex gradients
svg-to-drawio diagram.svg --filter-policy prefer-native --gradient-policy prefer-native

# Use parallel workers for a larger batch
svg-to-drawio src/ --recursive --workers 4 --overwrite

# Pipe draw.io XML directly into another tool
svg-to-drawio diagram.svg --stdout > diagram.drawio

# Flatten all groups into a single layer
svg-to-drawio diagram.svg --flatten --overwrite
```

During a normal conversion run, the CLI prints a short compatibility summary and mainly highlights rows that were not fully native. `--analyze` prints the full per-file compatibility matrix, and `--report-json` writes the same data in machine-readable form for CI, automation, or custom tooling. See the [compatibility reference](reference.md) for what each status means.
