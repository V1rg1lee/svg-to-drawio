# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [3.9.1] - 2026-06-20

### Fixed

- Corrected the macOS DMG background dimensions to match the `660x400` Finder window, keeping its artwork and drag-to-Applications guidance properly positioned.
- Restored the mounted-volume icon by installing `.VolumeIcon.icns` directly on the writable mounted image and applying its `icnC`, invisible, and custom-volume attributes before final compression.
- Strengthened macOS packaging checks so CI validates the DMG background dimensions and fails when the configured mounted-volume icon is missing from the finished image.

## [3.9.0] - 2026-06-20

### Added

- macOS DMG releases now include a custom Finder background, arranged application and `/Applications` icons, a dedicated mounted-volume icon, and a custom icon for the `.dmg` file itself.
- The desktop app can now cancel an active conversion with the Escape key and generates its equivalent CLI command through a dedicated, testable command builder.
- CI now detects whether desktop-related files changed before running the expensive cross-platform desktop packaging jobs.
- Diagnostic issue codes are now centralized, with additional regression coverage for converter state isolation, CSS indexing, malformed paths, rendering caches, CLI validation, desktop conversion, and DMG packaging.

### Changed

- CSS rules are indexed before style application, reducing repeated selector scans while preserving the existing cascade behavior.
- Converter internals were reorganized to reduce duplicated rendering-policy logic and improve repeated bounds and compatibility calculations.
- `--require-native` now accepts comma-separated capability names or repeated flags without accidentally consuming the input SVG path.
- Desktop preview rendering now follows the selected text metrics policy more consistently.
- Development tools are pinned to the same Ruff and mypy versions used by pre-commit, while desktop dependencies now use bounded major-version ranges.

### Fixed

- `--stdout` now rejects incompatible analysis, watch, report, and quality-gate options instead of silently ignoring them.
- Non-interactive CLI execution without an input path now exits with a clear error instead of attempting to prompt.
- The CLI now explains when `--workers` is ignored in sequential analysis or watch modes.
- Forced desktop shutdown now gives cooperative cancellation a short opportunity to finish, reducing the risk of truncated output files.
- macOS DMG styling failures now degrade gracefully with explicit warnings, use the actual mount point instead of an assumed volume name, verify Finder metadata, and retry detachment while Finder flushes `.DS_Store`.

## [3.8.1] - 2026-06-20

### Changed

- macOS DMG builds now keep the app icon and DMG icon separate, and also attempt to apply the dedicated `dmg_volume.icns` icon to the DMG file itself, not just the mounted volume contents.

## [3.8.0] - 2026-06-20

### Changed

- Windows portable desktop release artifacts now ship as direct `.exe` files instead of `.zip` archives.
- macOS desktop release artifacts now ship as universal2 `.dmg` disk images instead of `macos.zip` archives, and the app bundle now uses the Finder-friendly name `SVG to draw.io.app`.

## [3.7.0] - 2026-06-19

### Added

- An interactive desktop preview experience with source SVG rendering, draw.io-oriented preview rendering, zooming, compatibility highlights, and batch preview selection.
- Preview-specific text rendering support for advanced cases such as `textPath`, positioned glyphs, and compatibility annotations inside the desktop app.
- A shared reusable desktop packaging workflow for CI and release builds, plus site fingerprinting to avoid unnecessary GitHub Pages deployments.
- Additional regression coverage for desktop preview rendering, CLI/API quality gates, polygon clipping, CSS edge cases, packaging smoke tests, and documentation fingerprinting.

### Changed

- Polished the desktop UI with improved selectors, dialogs, expandable sections, preview controls, and cleaner logging behavior.
- Consolidated desktop packaging logic so pull request validation and release packaging now share the same workflow definition.
- Updated build and documentation dependencies, including PyInstaller, PySide6, mkdocstrings, pinned GitHub Actions steps, and release tooling.

### Fixed

- Hardened engine edge cases around transforms, polygon clipping, CSS/style resolution, shape emission, and preview asset handling.
- Improved CLI and Python API input validation, and clarified quality gate messaging around score thresholds and rendering requirements.
- Fixed CI startup issues caused by reusable workflow permission mismatches and reduced unnecessary GitHub Pages deployment churn.

## [3.6.0] - 2026-06-19

### Added

- A shared capability registry with richer compatibility reporting across the engine, CLI, Python API, and desktop app.
- Advanced rendering presets and policy controls shared conceptually across all interfaces.
- Native handling for simple clipping and simple editable pattern cases, alongside expanded text and `textPath` support.
- Cross-platform smoke tests for packaged desktop deliverables, plus shared Linux packaging helper scripts.
- Additional regression coverage and fixture updates for rendering, packaging, diagnostics, and text handling.
- Community and governance files: `CONTRIBUTING.md`, `CONTRIBUTORS.md`, issue templates, a Code of Conduct, and a Security Policy.

### Changed

- Improved rendering compatibility messaging so users can better understand what stays editable, what is approximated, and what falls back to embedded SVG.
- Refined desktop, CLI, API, and documentation alignment around rendering policies and compatibility behavior.
- Updated Linux packaging flows to better support release validation and portable desktop bundles.

### Fixed

- Restored faithful fallback behavior for plain Gaussian blur cases instead of over-aggressive native approximation.
- Hardened simple pattern handling so unsupported artwork falls back safely instead of producing misleading native output.
- Improved Linux artifact smoke testing to validate the actual archive layouts produced by the build pipeline.

## [3.5.1] - 2026-06-18

### Added

- Linux RPM packaging built inside a Fedora container, so the packaged runtime matches Fedora/openSUSE/RHEL-like ABI expectations instead of reusing the Debian/Ubuntu bundle.

## [3.5.0] - 2026-06-18

### Added

- Packaging scripts for Linux (`.deb`, `.rpm`, `.flatpak`, `.AppImage`) and Windows installer builds.
- Quality gate options for CI: `--fail-on-warning`, `--fail-on-fallback`, `--min-score`, `--require-native`.
- GitHub Pages documentation site (MkDocs + Material).

## [3.4.0] - 2026-06-17

### Changed

- CLI restructured as an installable package with a console entry point (`svg-to-drawio`) declared in `pyproject.toml`.

### Added

- Compatibility tests and enhanced SVG feature reporting.
- CI/CD workflow improvements.

## [3.3.0] - 2026-06-17

### Added

- Gradient rendering policies (`auto`, `prefer-native`, `prefer-fallback`).
- CSS custom property support (`var(--name, fallback)`).
- Structured diagnostics and fallback reporting.
- Path simplification tests.

## [3.2.1] - 2026-06-16

### Fixed

- Windows installer output filename.

## [3.2.0] - 2026-06-15

### Added

- Dark mode theme for the desktop app.
- Windows installer (Inno Setup) and Linux AppImage packaging.

### Changed

- Desktop app UI: scroll area and logging improvements.

## [3.1.0] - 2026-06-15

### Added

- Desktop GUI (PySide6).
- `--watch`, `--flatten`, and `--stdout` CLI flags.
- Python API (`convert_file`, `convert_to_string`, and related entry points).

## [3.0.0] - 2026-06-14

### Changed

- Modular rewrite of the conversion engine (`StyleBuilder`, `EmitterContext`, and the path parser split into dedicated modules). Internal structure changed enough to warrant a major version bump.

## [2.2.0] - 2026-06-14

### Added

- `<image>` element support (local SVG and PNG assets).

### Changed

- SVG regression test fixture extended with new markers and additional features.

## [2.1.0] - 2026-06-14

### Changed

- SVG regression test fixture enhanced with new features and adjustments.

## [2.0.0] - 2026-06-14

### Added

- Comprehensive SVG test fixture used as a regression baseline.

## [1.0.0] - 2026-06-13

### Added

- Initial release: SVG to draw.io conversion engine.

[Unreleased]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.8.1...HEAD
[3.8.1]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.8.0...v3.8.1
[3.8.0]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.7.0...v3.8.0
[3.7.0]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.6.0...v3.7.0
[3.6.0]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.5.1...v3.6.0
[3.5.1]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.5.0...v3.5.1
[3.5.0]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.4.0...v3.5.0
[3.4.0]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.3.0...v3.4.0
[3.3.0]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.2.1...v3.3.0
[3.2.1]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.2.0...v3.2.1
[3.2.0]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.1.0...v3.2.0
[3.1.0]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/V1rg1lee/svg-to-drawio/compare/v2.2.0...v3.0.0
[2.2.0]: https://github.com/V1rg1lee/svg-to-drawio/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/V1rg1lee/svg-to-drawio/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/V1rg1lee/svg-to-drawio/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/V1rg1lee/svg-to-drawio/releases/tag/v1.0.0
