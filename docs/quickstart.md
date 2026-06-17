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

By default, output is written next to the source file (`diagram.svg` -> `diagram.drawio`).

Running from a repository checkout instead of an installed package works the same way:

```bash
python main.py diagram.svg
python main.py path/to/folder/ --recursive --overwrite
```

## Desktop app

For anyone who would rather drag, drop, and click than type commands. The desktop app uses the exact same conversion engine as the CLI and Python API, so there is no difference in output quality.

Download a release artifact from the [Releases page](https://github.com/V1rg1lee/svg-to-drawio/releases):

- Windows: `Setup.exe` installer (auto-upgrades an existing install) or a plain `.zip` for advanced users
- Linux: portable `.AppImage` or a plain `.tar.gz`
- macOS: `.zip` archive of the app bundle

Features: drag-and-drop, multi-root queues, live progress, cooperative cancellation, safe close / force close, one-click output folder access, watch mode, persistent preferences, rendering presets, copy-as-CLI command, a plain-English compatibility panel with clickable details, and JSON report export.

Run it from source instead:

```bash
pip install -r requirements-desktop.txt
python desktop_app.py
```

## Where next

- [CLI reference](cli.md) for every command-line option.
- [Python API](python-api.md) to call the engine from your own code.
