# Quick start

**Requirements:** Python 3.11+, no external runtime dependency for the CLI.

```bash
pip install svg-to-drawio
svg-to-drawio diagram.svg
```

If you want the optional event-driven watch mode instead of polling:

```bash
pip install "svg-to-drawio[watch]"
```

If you want the best available text sizing backend in library / CLI environments too:

```bash
pip install "svg-to-drawio[text-metrics]"
```

By default, output is written next to the source file (`diagram.svg` -> `diagram.drawio`).

Running from a repository checkout instead of an installed package works the same way:

```bash
python main.py diagram.svg
python main.py path/to/folder/ --recursive --overwrite
```

## Desktop app

For anyone who would rather drag, drop, and click than type commands. The desktop app uses the exact same conversion engine as the CLI and Python API, so there is no difference in output quality.

Download a release artifact from the [Releases page](https://github.com/V1rg1lee/svg-to-drawio/releases):

- Windows: `x64` and `ARM64` builds, each available as a `Setup.exe` installer or a direct portable `.exe`
- Linux: `x64` and `ARM64` builds across `.deb`, `.rpm`, `.flatpak`, portable `.AppImage`, and plain `.tar.gz`
- macOS: universal2 `.dmg` disk image for Apple Silicon and Intel Macs

| Platform | Architecture | Recommended download | Other available formats |
|---|---|---|---|
| Windows | `x64` | `windows-x64-setup.exe` | `windows-x64.exe` |
| Windows | `ARM64` | `windows-arm64-setup.exe` | `windows-arm64.exe` |
| Linux (Debian / Ubuntu family) | `x64` | `linux-amd64.deb` | `linux-x86_64.flatpak`, `linux-x64.AppImage`, `linux-x64.tar.gz` |
| Linux (Debian / Ubuntu family) | `ARM64` | `linux-arm64.deb` | `linux-aarch64.flatpak`, `linux-arm64.AppImage`, `linux-arm64.tar.gz` |
| Linux (Fedora / openSUSE / RHEL-like) | `x64` | `linux-x86_64.rpm` | `linux-x86_64.flatpak`, `linux-x64.AppImage`, `linux-x64.tar.gz` |
| Linux (Fedora / openSUSE / RHEL-like) | `ARM64` | `linux-aarch64.rpm` | `linux-aarch64.flatpak`, `linux-arm64.AppImage`, `linux-arm64.tar.gz` |
| Linux (cross-distro) | `x64` | `linux-x86_64.flatpak` | `linux-x64.AppImage`, `linux-x64.tar.gz` |
| Linux (cross-distro) | `ARM64` | `linux-aarch64.flatpak` | `linux-arm64.AppImage`, `linux-arm64.tar.gz` |
| macOS | `universal2` | `macos.dmg` | none |

Features: drag-and-drop, multi-root queues, live progress, cooperative cancellation, safe close / force close, one-click output folder access, watch mode, persistent preferences, rendering presets, merging multiple SVGs into one file (pages or tile grid) with an optional notes legend / page background, copy-as-CLI command, a plain-English compatibility panel with clickable details, and JSON report export.

Release downloads also include checksum and provenance material. See [Desktop downloads](release-downloads.md) for package recommendations and verification steps.

Run it from source instead:

```bash
pip install -r requirements-desktop.txt
python desktop_app.py
```

## Where next

- [CLI reference](cli.md) for every command-line option.
- [Python API](python-api.md) to call the engine from your own code.
- [Interface parity](interface-parity.md) to compare the CLI, API, and desktop workflows.
- [Advanced rendering](advanced-rendering.md) for the shared presets and policy tradeoffs used by the CLI, API, and desktop app.
