# Security: Dependency Pinning for Release Builds

## Overview

The desktop release workflow (`desktop-packaging.yml`) executes with sensitive credentials including:
- Release GPG private key and passphrase (for signing artifacts)
- GitHub token with `contents: write` permission (for publishing releases)

To prevent supply chain attacks where malicious code in dependencies could steal these credentials or tamper with releases, all executable dependencies are cryptographically pinned.

## Hash-Pinned Dependencies

### Python Dependencies

The workflow uses `requirements-desktop.lock` instead of `requirements-desktop.txt` for release builds. This lockfile:

1. **Pins exact versions** - No version ranges that could resolve to newer, potentially compromised packages
2. **Includes cryptographic hashes** - Each package wheel is verified against SHA256 hashes
3. **Covers transitive dependencies** - All indirect dependencies are also pinned and hashed
4. **Uses `--require-hashes` flag** - pip will refuse to install any package without a matching hash

### Inno Setup (Windows Installer Tool)

The Chocolatey installation of Inno Setup is pinned to:
- **Specific version**: 6.3.3 (update as needed, but never use "latest")
- **SHA256 checksum**: Verified during installation
- **Checksum type**: Explicitly specified to prevent downgrade attacks

## Maintaining the Lockfile

### When to Regenerate

Regenerate `requirements-desktop.lock` when:
- Updating minimum versions in `requirements-desktop.txt`
- Security advisories require dependency updates
- Adding or removing dependencies
- Periodically (e.g., quarterly) to get security patches

### How to Regenerate

```bash
# Install pip-tools
pip install pip-tools

# Generate the lockfile with hashes
pip-compile --generate-hashes --output-file=requirements-desktop.lock requirements-desktop.txt

# Verify the lockfile works
pip install --require-hashes -r requirements-desktop.lock
```

### Important Notes

1. **Review changes carefully** - When regenerating, review the diff to ensure no unexpected packages were added
2. **Test before committing** - Verify the desktop build still works with the new lockfile
3. **Document major updates** - If updating to a new major version, note it in the commit message
4. **Never skip hash verification** - The `--require-hashes` flag is critical for security

## Updating Inno Setup Version

To update the Inno Setup version:

1. Check the [Chocolatey package page](https://community.chocolatey.org/packages/innosetup) for available versions
2. Download the package and verify its checksum:
   ```powershell
   choco download innosetup --version=X.Y.Z
   # Check the .nupkg file hash
   Get-FileHash innosetup.X.Y.Z.nupkg -Algorithm SHA256
   ```
3. Update the version and checksum in `desktop-packaging.yml`
4. Test the Windows build locally or in CI

## Threat Model

This mitigation addresses:

- **Compromised PyPI packages** - Attacker publishes malicious version of a dependency
- **Typosquatting** - Attacker publishes package with similar name
- **Dependency confusion** - Attacker exploits package resolution to inject malicious code
- **Tool compromise** - Attacker compromises pip or Chocolatey to serve malicious packages
- **Man-in-the-middle attacks** - Network attacker intercepts package downloads

By requiring exact versions with cryptographic hashes, the workflow will fail rather than execute untrusted code with signing credentials.

## Related Security Measures

- GitHub Actions are pinned to commit SHAs (not tags) to prevent tag-moving attacks
- Credentials are only exposed to the specific job that needs them
- Artifacts are smoke-tested before publication
- Release verification steps ensure tag matches package version

## References

- [pip hash-checking mode](https://pip.pypa.io/en/stable/topics/secure-installs/)
- [pip-tools documentation](https://pip-tools.readthedocs.io/)
- [Chocolatey package checksums](https://docs.chocolatey.org/en-us/choco/commands/install#options-and-switches)
- [Supply chain security best practices](https://slsa.dev/)
