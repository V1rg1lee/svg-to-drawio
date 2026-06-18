## What and why

<!-- One logical change per PR. Describe the change and the reason for it. -->

## Checklist

- [ ] `python -m unittest discover -s tests -v` passes
- [ ] `python -m ruff check main.py svg_to_drawio svg_to_drawio_desktop tests` is clean
- [ ] `python -m mypy` is clean
- [ ] If conversion output changed: fixtures regenerated with `python -m tests.regenerate_fixtures` and the reason is explained below
- [ ] If a CLI flag, Python API function, or default behavior changed: `README.md` is updated
- [ ] If a CLI flag, Python API function, or default behavior changed: the relevant GitHub Pages doc under `docs/` (`quickstart.md`, `cli.md`, `python-api.md`, `advanced-rendering.md`) is updated and builds with `python scripts/build_docs.py build --strict`

## Fixture / behavior changes (if any)

<!-- Why the conversion output changed, if it did. Delete this section if not applicable. -->
