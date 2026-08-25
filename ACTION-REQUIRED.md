# IMPORTANT: Action Required Before Next Release

## Security Fix Applied

This repository has been patched to mitigate a supply chain attack vulnerability in the desktop release workflow. The workflow previously installed mutable dependencies while signing credentials were available in the environment.

## Required Action

Before the next release build, you **MUST** generate the hash-pinned requirements lockfile:

```bash
python scripts/generate_requirements_lock.py
```

This will:
1. Install pip-tools if needed
2. Resolve all dependencies to exact versions
3. Generate requirements-desktop.lock with SHA256 hashes for all packages
4. Include all transitive dependencies

## Verification

After generating, verify it works:

```bash
# Test installation
pip install --require-hashes -r requirements-desktop.lock

# Test desktop build
python build_desktop.py
```

## Commit the Lockfile

Once generated and tested:

```bash
git add requirements-desktop.lock
git commit -m "Add hash-pinned requirements lockfile for secure builds"
git push
```

## What Changed

1. **Python dependencies**: Now installed with `--require-hashes` from a lockfile
2. **pip upgrade removed**: No longer upgrades pip to latest before installation
3. **Inno Setup pinned**: Version 6.3.3 instead of latest

## Why This Matters

The release workflow has access to:
- GPG private key and passphrase (for signing artifacts)
- GitHub token with write access (for publishing releases)

Without hash pinning, a compromised or malicious package could:
- Steal signing credentials
- Modify release artifacts
- Publish attacker-controlled releases

Hash pinning ensures packages match expected cryptographic hashes, preventing these attacks.

## Documentation

See [SECURITY-DEPENDENCY-PINNING.md](SECURITY-DEPENDENCY-PINNING.md) for complete documentation.

## Questions?

If you have questions about this security fix, please review:
- SECURITY-FIX-SUMMARY.md - Detailed explanation of changes
- SECURITY-DEPENDENCY-PINNING.md - Ongoing maintenance procedures
- scripts/README.md - Script documentation

---

**This file can be deleted after the lockfile is generated and committed.**
