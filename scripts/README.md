# Scripts Directory

This directory contains utility scripts for maintaining the svg-to-drawio project.

## Security Scripts

### generate_requirements_lock.py

Generates `requirements-desktop.lock` with cryptographic hash pinning for all dependencies.

**Purpose**: The desktop release workflow executes with sensitive signing credentials (GPG private key and passphrase) and GitHub tokens with write access. To prevent supply chain attacks where malicious code in dependencies could steal these credentials or tamper with releases, all dependencies must be cryptographically pinned with SHA256 hashes.

**Usage**:
```bash
python scripts/generate_requirements_lock.py
```

**When to run**:
- After modifying `requirements-desktop.txt`
- Periodically (e.g., quarterly) to get security updates
- When security advisories require dependency updates

**What it does**:
1. Installs `pip-tools` if not already installed
2. Runs `pip-compile --generate-hashes` to resolve all dependencies
3. Generates `requirements-desktop.lock` with exact versions and SHA256 hashes
4. Includes all transitive dependencies with platform-specific wheel hashes

**Verification**:
After generating, verify the lockfile works:
```bash
pip install --require-hashes -r requirements-desktop.lock
```

The CI workflow `.github/workflows/validate-lockfile.yml` automatically checks that the lockfile is valid and up-to-date on pull requests.

## Other Scripts

### generate_release_gpg_key.py

Generates a GPG key pair for signing release artifacts (AppImages, etc.).

### build_docs.py

Builds the project documentation.

### site_fingerprint.py

Generates fingerprints for site verification.
