# Desktop downloads

The desktop app uses the exact same conversion engine as the CLI and Python API. The only thing that changes across release assets is packaging, platform integration, and how convenient the install flow is for a given operating system.

## Which download should I choose?

| Platform | Architecture | Recommended download | Other available formats |
|---|---|---|---|
| Windows | `x64` | `windows-x64-setup.exe` | `windows-x64.zip` |
| Windows | `ARM64` | `windows-arm64-setup.exe` | `windows-arm64.zip` |
| Linux (Debian / Ubuntu family) | `x64` | `linux-amd64.deb` | `linux-x86_64.flatpak`, `linux-x64.AppImage`, `linux-x64.tar.gz` |
| Linux (Debian / Ubuntu family) | `ARM64` | `linux-arm64.deb` | `linux-aarch64.flatpak`, `linux-arm64.AppImage`, `linux-arm64.tar.gz` |
| Linux (Fedora / openSUSE / RHEL-like) | `x64` | `linux-x86_64.rpm` | `linux-x86_64.flatpak`, `linux-x64.AppImage`, `linux-x64.tar.gz` |
| Linux (Fedora / openSUSE / RHEL-like) | `ARM64` | `linux-aarch64.rpm` | `linux-aarch64.flatpak`, `linux-arm64.AppImage`, `linux-arm64.tar.gz` |
| Linux (cross-distro) | `x64` | `linux-x86_64.flatpak` | `linux-x64.AppImage`, `linux-x64.tar.gz` |
| Linux (cross-distro) | `ARM64` | `linux-aarch64.flatpak` | `linux-arm64.AppImage`, `linux-arm64.tar.gz` |
| macOS | bundled app archive | `macos.zip` | none |

## Short guidance

- Choose `Setup.exe` on Windows unless you explicitly want a portable zip.
- Choose `.deb` on Debian, Ubuntu, Linux Mint, Pop!_OS, and close derivatives.
- Choose `.rpm` on Fedora, openSUSE, and RHEL-like systems.
- Choose `.flatpak` when you want a cross-distro Linux install flow.
- Choose `.AppImage` when you prefer a single portable Linux file instead of an installed package.
- Choose `.tar.gz` only if you specifically want the raw extracted bundle.

## Release verification

Public releases now ship with a small set of verification assets:

- `SHA256SUMS.txt`
- `SHA256SUMS.txt.sigstore.json`
- `SHA256SUMS.txt.asc` when GPG signing is enabled
- `svg-to-drawio-release-signing-key.asc` when GPG signing is enabled
- `svg-to-drawio-<version>-verification-bundles.zip` for advanced per-artifact verification

The recommended verification flow is to verify the checksum manifest once, then verify the downloaded file against that manifest.

```bash
cosign verify-blob SHA256SUMS.txt \
  --bundle SHA256SUMS.txt.sigstore.json \
  --certificate-identity "https://github.com/V1rg1lee/svg-to-drawio/.github/workflows/desktop-build.yml@refs/tags/v3.3.0" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com"

sha256sum -c SHA256SUMS.txt
```

If GPG assets are present:

```bash
gpg --import svg-to-drawio-release-signing-key.asc
gpg --verify SHA256SUMS.txt.asc SHA256SUMS.txt
```

The advanced archive `svg-to-drawio-<version>-verification-bundles.zip` contains:

- one Sigstore bundle per artifact (`*.sigstore.json`)
- detached `*.AppImage.asc` files when GPG signing is enabled

Use that archive only if you want artifact-by-artifact verification instead of the simpler manifest-first flow above.

## Notes

- AppImages can also carry an embedded GPG signature when signing is enabled in the release workflow.
- These checks improve provenance and integrity verification, but they do not replace Windows Authenticode / SmartScreen trust or macOS notarization.
- `.deb`, `.rpm`, and `.flatpak` are published as standalone release files here, not through a full package repository or app store.
