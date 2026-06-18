# Python API

```python
from svg_to_drawio import RenderingOptions, convert_file, convert_file_result, convert_to_string

# Write to disk and get the output path back
out = convert_file("diagram.svg")

# Or keep the XML + structured report together
result = convert_file_result("diagram.svg")
print(result.output_path)
print(result.compatibility_score)
print(result.report.compatibility_overview.headline)

# Return draw.io XML as a string without writing a file
xml = convert_to_string(
    "diagram.svg",
    rendering_options=RenderingOptions(
        gradient_policy="prefer-native",
        filter_policy="prefer-native",
        text_metrics_policy="heuristic",
    ),
)
```

[`convert_file_result`](api-reference.md#svg_to_drawio.convert_file_result), [`convert_to_string_result`](api-reference.md#svg_to_drawio.convert_to_string_result), [`convert_svg_string_result`](api-reference.md#svg_to_drawio.convert_svg_string_result), and [`convert_svg_bytes_result`](api-reference.md#svg_to_drawio.convert_svg_bytes_result) all return a [`ConversionResult`](api-reference.md#svg_to_drawio.ConversionResult) pairing the output with its full diagnostics report, instead of just a path or a string.

The same beginner-friendly presets exposed by the desktop app are also available programmatically:

```python
from svg_to_drawio import rendering_preflight_lines, rendering_preset_options

options = rendering_preset_options("editability")
for line in rendering_preflight_lines(options):
    print(line)
```

## In-memory conversions

For web backends, notebooks, or CI transforms that already hold SVG content in memory rather than on disk:

```python
from svg_to_drawio import convert_svg_string_result

result = convert_svg_string_result(
    '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40">'
    '<rect x="0" y="0" width="80" height="40" fill="#2563eb" />'
    "</svg>",
    title="memory-diagram",
)
print(result.xml)
print(result.report.to_dict()["schema_version"])
```

`convert_svg_string` / `convert_svg_bytes` are the plain-XML equivalents when you don't need the full result object.

## Batch conversions

With progress reporting and cancellation:

```python
from svg_to_drawio import ConversionOptions, ConversionService

service = ConversionService()
summary = service.convert(
    ["folder/", "other.svg"],
    ConversionOptions(output_dir="out/", recursive=True, overwrite=True),
    reporter=lambda event: print(event.message),
)
print(summary.to_status_line())
```

## Diagnostics without writing output

```python
from svg_to_drawio import analyze_file

report = analyze_file("diagram.svg")
print(report.compatibility_score)
print(report.compatibility_overview.headline)
print(report.compatibility_overview.summary)
for row in report.compatibility_matrix:
    print(row.label, row.status_label, row.message)
for issue in report.issues:
    print(issue.message)
```

## Convert and inspect the report afterwards

```python
from svg_to_drawio import Converter

converter = Converter()
converter.convert_file("diagram.svg")
report = converter.get_report()
payload = report.to_dict()  # JSON-friendly diagnostics + compatibility data
```

## Quality gates for CI

`evaluate_quality_gates` is the Python equivalent of the CLI's `--fail-on-warning`, `--fail-on-fallback`, `--min-score`, and `--require-native` flags:

```python
from svg_to_drawio import QualityGateOptions, convert_svg_string_result, evaluate_quality_gates

result = convert_svg_string_result(svg_text, title="ci-check")
violations = evaluate_quality_gates(
    [result.report],
    QualityGateOptions(fail_on_fallback=True, min_score=90, require_native=("text",)),
)
if violations:
    raise SystemExit(1)
```

`require_native` accepts any of the capability keys returned by [`capability_keys`](api-reference.md#svg_to_drawio.capability_keys) (for example `text`, `gradients`, `filters`, `clipping`, `patterns`, `markers`, `images`, `references`).

See the [API reference](api-reference.md) for the full signature of every public class and function, and [Advanced rendering](advanced-rendering.md) for what each `RenderingOptions` policy does.
