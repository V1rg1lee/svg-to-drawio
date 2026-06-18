# Security policy

## Supported versions

Only the latest version published on [PyPI](https://pypi.org/project/svg-to-drawio/) and the latest GitHub release are supported. There is no LTS branch - upgrade to get a fix.

## Reporting a vulnerability

Do not open a public issue for security vulnerabilities. Instead, use GitHub's private reporting:

1. Go to the [Security tab](https://github.com/V1rg1lee/svg-to-drawio/security) of this repository.
2. Click **Report a vulnerability**.
3. Describe the issue: affected version, a minimal SVG or command that triggers it, and the impact.

This is a single-maintainer project, so there's no guaranteed SLA, but reports are read and triaged as soon as possible.

## Scope

In scope:

- The conversion engine, CLI, and Python API (`svg_to_drawio/`) - e.g. XML parsing issues (XXE, entity expansion), path traversal through `<image>` asset resolution, or a malicious SVG causing unbounded resource use.
- The desktop app (`svg_to_drawio_desktop/`).
- The release/build pipeline (GitHub Actions workflows, packaging scripts) - e.g. supply-chain issues like unpinned actions or unsigned artifacts.

Out of scope:

- Vulnerabilities in draw.io / app.diagrams.net itself - report those to the [drawio project](https://github.com/jgraph/drawio).
- Vulnerabilities that require an already-malicious local SVG file you intentionally chose to convert with admin/root privileges you already have.

See [Release authenticity](README.md#release-authenticity) in the README for how to verify the integrity of downloaded release artifacts.
