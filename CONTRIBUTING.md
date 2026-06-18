# Contributing

This project converts SVG files into editable draw.io diagrams - as a CLI, a Python library, and a desktop app sharing the same conversion engine. It targets Python 3.11+. If your contribution is outside that scope (a different output format, a different input format, a web service, etc.), open an issue first to discuss it before writing code.

## Setup

```bash
pip install -r requirements-dev.txt
python -m pre_commit install --hook-type pre-commit --hook-type pre-push
```

This installs `ruff`, `mypy`, `pre-commit`, `build`, and `twine`, and wires up the Git hooks: `ruff check` + `ruff format` + `mypy` run on every commit, the full `unittest` suite runs on every push.

## Making a change

```bash
python -m unittest discover -s tests -v
python -m ruff check main.py svg_to_drawio svg_to_drawio_desktop tests
python -m mypy
```

Run all three before opening a PR - `pre_commit run --all-files` runs the same checks (minus the test suite) in one shot. GitHub Actions runs the same pipeline remotely, so a clean local run means CI should pass too.

If your change affects conversion output, the regression fixtures (`tests/fixtures/test_all_features.svg` / `.drawio`) may need regenerating:

```bash
python -m tests.regenerate_fixtures
```

The fixture baseline is generated with `text_metrics_policy="heuristic"` on purpose, so it stays identical across Windows, Linux, and CI runners regardless of installed system fonts. Don't regenerate it with a different policy.

Tests live under `tests/unit/` (rendering, styles, transforms, compatibility, fuzzing) and `tests/integration/` (CLI, end-to-end conversions, the conversion service). Add tests next to the existing ones that cover the same area rather than creating a new top-level test module.

## Reporting a bug

Open an issue with:

- The smallest SVG snippet that reproduces the problem - not your full production file. If you can't shrink it, attach the original, but try first; a 10-line repro gets fixed faster than a 2000-line one.
- The exact command or API call you ran.
- What you expected vs. what you got (the generated `.drawio` content, a CLI error message, or a screenshot of the result in draw.io).
- Your OS and Python version (`python --version`).

If the bug is about a specific SVG feature not rendering as expected, run with `--analyze` first - it often tells you whether the converter already knows it's falling back, which changes the nature of the bug report:

```bash
svg-to-drawio your-file.svg --analyze
```

## Proposing a feature

Open an issue before writing code. Describe the SVG input and the draw.io output you expect, and why the current fallback behavior isn't good enough. Features that significantly increase scope (new file formats, new runtime dependencies, GUI-only features with no CLI/API equivalent) need agreement on the approach before a PR, to avoid throwaway work.

## Pull requests

- One logical change per PR.
- Tests pass, `ruff check`, `ruff format`, and `mypy` are clean.
- If you changed conversion output, update or regenerate the fixtures and explain why in the PR description.
- Update `README.md` if you added a CLI flag, Python API function, or changed default behavior.
- Update the GitHub Pages docs under `docs/` (`quickstart.md`, `cli.md`, `python-api.md`, `advanced-rendering.md`) for the same change. The API reference page is generated from docstrings via mkdocstrings, but the hand-written pages are not - they only change if you edit them. Verify locally with `python scripts/build_docs.py build --strict` before pushing; the site auto-deploys to GitHub Pages on merge to `main` (see `.github/workflows/docs.yml`).

Contributors are listed in [CONTRIBUTORS.md](CONTRIBUTORS.md).
