# Security Fix Implementation Checklist

## Immediate Actions (Before Next Release)

- [ ] Generate the hash-pinned lockfile:
  ```bash
  python scripts/generate_requirements_lock.py
  ```

- [ ] Verify the lockfile works:
  ```bash
  pip install --require-hashes -r requirements-desktop.lock
  ```

- [ ] Test the desktop build:
  ```bash
  python build_desktop.py
  ```

- [ ] Commit and push the lockfile:
  ```bash
  git add requirements-desktop.lock
  git commit -m "Add hash-pinned requirements lockfile for secure builds"
  git push
  ```

- [ ] Verify CI passes with the new lockfile

- [ ] Test a release build (if possible in a test environment)

## Verification

- [ ] Confirm `.github/workflows/desktop-packaging.yml` no longer upgrades pip
- [ ] Confirm workflow uses `--require-hashes` flag
- [ ] Confirm Inno Setup is pinned to version 6.3.3
- [ ] Confirm `requirements-desktop.lock` exists and contains valid hashes
- [ ] Confirm validate-lockfile.yml workflow is active

## Documentation Review

- [ ] Read [SECURITY-DEPENDENCY-PINNING.md](SECURITY-DEPENDENCY-PINNING.md)
- [ ] Understand when to regenerate the lockfile
- [ ] Know how to update Inno Setup version if needed

## Ongoing Maintenance

- [ ] Add calendar reminder to regenerate lockfile quarterly
- [ ] Watch for security advisories affecting dependencies
- [ ] Update lockfile when modifying requirements-desktop.txt

## Optional Cleanup

After completing the above:

- [ ] Delete ACTION-REQUIRED.md
- [ ] Delete SECURITY-FIX-SUMMARY.md (or move to docs/)
- [ ] Delete this checklist

## Questions or Issues?

If you encounter problems:

1. Check that pip-tools is installed: `pip install pip-tools`
2. Try regenerating manually: `pip-compile --generate-hashes --output-file=requirements-desktop.lock requirements-desktop.txt`
3. Verify Python 3.11 is being used
4. Check for network issues preventing package downloads

## Success Criteria

✓ Lockfile generated with hashes for all dependencies
✓ Desktop build completes successfully
✓ CI workflows pass
✓ Release workflow uses hash verification
✓ No pip upgrade in release workflow
✓ Inno Setup version pinned

---

**Status**: ⚠️ PENDING - Lockfile generation required before next release
