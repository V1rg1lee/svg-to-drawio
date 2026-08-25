# Security Fix: Supply Chain Attack Mitigation

## Summary

This patch mitigates supply chain attacks in the desktop release workflow by implementing cryptographic hash pinning for all Python dependencies and version pinning for the Inno Setup installer tool.

## Changes Made

### 1. Workflow Changes (`.github/workflows/desktop-packaging.yml`)

**Removed:**
- `python -m pip install --upgrade pip` - Eliminated mutable pip upgrade that could execute malicious code
- `python -m pip install -r requirements-desktop.txt` - Replaced with hash-verified installation
- `choco install innosetup` (unversioned) - Replaced with version-pinned installation

**Added:**
- Hash-verified dependency installation using `--require-hashes` flag
- Validation check that ensures lockfile exists before proceeding
- Version-pinned Inno Setup installation (6.3.3)
- Comprehensive security comments explaining the measures

### 2. New Files Created

**`requirements-desktop.lock`**
- Hash-pinned lockfile template for desktop dependencies
- Contains placeholder structure showing required format
- Must be generated with actual hashes using `pip-compile --generate-hashes`
- Includes clear instructions for regeneration

**`scripts/generate_requirements_lock.py`**
- Automated script to generate the hash-pinned lockfile
- Installs pip-tools if needed
- Runs pip-compile with hash generation
- Provides verification instructions

**`SECURITY-DEPENDENCY-PINNING.md`**
- Comprehensive documentation of the security measures
- Explains the threat model and mitigation strategy
- Provides maintenance procedures for the lockfile
- Documents how to update Inno Setup version

**`.github/workflows/validate-lockfile.yml`**
- CI workflow to validate lockfile on pull requests
- Checks lockfile exists and contains valid hashes
- Verifies lockfile is up-to-date with requirements-desktop.txt
- Tests installation with hash verification

**`scripts/README.md`**
- Documentation for all scripts in the scripts directory
- Explains when and how to use generate_requirements_lock.py

### 3. Updated Files

**`requirements-desktop.txt`**
- Added security notice and regeneration instructions
- Clarified that lockfile should be used for release builds

**`SECURITY.md`**
- Added reference to SECURITY-DEPENDENCY-PINNING.md
- Links supply-chain security documentation

## Security Impact

### Before
- Python dependencies resolved to latest versions within broad ranges
- pip upgraded to latest version before dependency installation
- Inno Setup installed without version pinning
- All operations executed with signing credentials in environment
- Malicious package code could:
  - Steal GPG private key and passphrase
  - Exfiltrate GitHub token with write access
  - Modify release artifacts
  - Publish attacker-controlled releases

### After
- All Python dependencies pinned to exact versions with SHA256 hashes
- pip not upgraded (uses version from Python installation)
- Inno Setup pinned to specific version (6.3.3)
- Hash verification ensures packages match expected cryptographic hashes
- Workflow fails if lockfile missing or invalid
- Supply chain attacks prevented by cryptographic verification

## Threat Model Addressed

This mitigation protects against:

1. **Compromised PyPI packages** - Attacker publishes malicious version
2. **Dependency confusion** - Attacker exploits package resolution
3. **Typosquatting** - Attacker publishes similar-named package
4. **Tool compromise** - Attacker compromises pip or Chocolatey
5. **Man-in-the-middle attacks** - Network attacker intercepts downloads

## Implementation Notes

### Lockfile Generation Required

The workflow will **intentionally fail** until `requirements-desktop.lock` is generated with actual hashes. This is by design to ensure the security measure is properly implemented.

To generate the lockfile:
```bash
python scripts/generate_requirements_lock.py
```

Or manually:
```bash
pip install pip-tools
pip-compile --generate-hashes --output-file=requirements-desktop.lock requirements-desktop.txt
```

### Inno Setup Version

Version 6.3.3 is pinned as a reasonable stable version. This should be updated periodically but never set to "latest". Chocolatey packages include embedded checksums that are automatically verified during installation.

### Maintenance

The lockfile should be regenerated:
- When requirements-desktop.txt is updated
- Periodically (e.g., quarterly) for security updates
- When security advisories require dependency updates

The validate-lockfile.yml workflow will automatically check that the lockfile is valid and up-to-date on pull requests.

## Testing

Before the first release build after this patch:

1. Generate the lockfile:
   ```bash
   python scripts/generate_requirements_lock.py
   ```

2. Test local installation:
   ```bash
   pip install --require-hashes -r requirements-desktop.lock
   ```

3. Test desktop build:
   ```bash
   python build_desktop.py
   ```

4. Commit the generated lockfile:
   ```bash
   git add requirements-desktop.lock
   git commit -m "Add hash-pinned requirements lockfile"
   ```

## References

- [pip hash-checking mode](https://pip.pypa.io/en/stable/topics/secure-installs/)
- [pip-tools documentation](https://pip-tools.readthedocs.io/)
- [SLSA Supply Chain Security](https://slsa.dev/)
- [Chocolatey package security](https://docs.chocolatey.org/en-us/choco/commands/install)
