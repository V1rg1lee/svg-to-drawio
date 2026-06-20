"""Build the CLI command equivalent to the desktop app's current settings.

Kept independent of Qt (plain dataclass in, string out) so the command-building
rules can be unit tested without constructing a QApplication or any widget.
"""

from __future__ import annotations

from dataclasses import dataclass

from svg_to_drawio.rendering_options import RenderingOptions


def quote_cli_arg(value: str) -> str:
    """Quote one CLI argument conservatively for copy-paste use."""
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


@dataclass(frozen=True)
class CliCommandOptions:
    """Plain snapshot of the desktop settings needed to build an equivalent CLI command."""

    sources: tuple[str, ...]
    output_dir: str | None
    recursive: bool
    overwrite: bool
    flatten: bool
    watch: bool
    use_cache: bool
    max_elements: int | None
    workers: int
    preset: str
    rendering_options: RenderingOptions


def build_equivalent_cli_command(options: CliCommandOptions) -> str:
    """Build a copy-paste-friendly `svg-to-drawio` command matching the given options."""
    args = ["svg-to-drawio"]
    args.extend(quote_cli_arg(source) for source in options.sources)
    if options.output_dir:
        args.extend(["--output-dir", quote_cli_arg(options.output_dir)])
    if options.recursive:
        args.append("--recursive")
    if options.overwrite:
        args.append("--overwrite")
    if options.flatten:
        args.append("--flatten")
    if options.watch:
        args.append("--watch")
    if not options.use_cache:
        args.append("--no-cache")
    if options.max_elements is not None:
        args.extend(["--max-elements", str(options.max_elements)])
    if options.workers > 1 and not options.watch:
        args.extend(["--workers", str(options.workers)])

    rendering_options = options.rendering_options
    if options.preset not in {"custom", "balanced"}:
        args.extend(["--rendering-preset", options.preset])
    else:
        if rendering_options.gradient_policy != "auto":
            args.extend(["--gradient-policy", rendering_options.gradient_policy])
        if rendering_options.filter_policy != "auto":
            args.extend(["--filter-policy", rendering_options.filter_policy])
        if rendering_options.text_metrics_policy != "auto":
            args.extend(["--text-metrics-policy", rendering_options.text_metrics_policy])
    return " ".join(args)
