# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/V1rg1lee/svg-to-drawio/compare/v3.5.1...HEAD
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
