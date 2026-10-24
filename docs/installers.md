# Installers

The repository scripts `install.sh` and `install.ps1` install a **published GitHub Release wheel** and its release-specific, hash-locked runtime dependency list. They:

1. Resolve the latest stable release or the exact version supplied in `PEKE_VERSION`.
2. Download the wheel, `requirements-hashed.txt`, and `SHA256SUMS` over HTTPS.
3. Verify the wheel and dependency lock against the manifest before installation.
4. Install the local Peke wheel into a pipx environment without resolving dependencies, then install runtime dependencies with pip's `--require-hashes` mode.

A missing or mismatched manifest entry causes installation to stop. No administrator elevation is used and model weights are never downloaded. The Peke wheel includes the SearXNG source and its runtime requirements, so the local Search & Research service does not require Docker; it still uses the Python environment required by this installer. Python 3.10+ and `pipx` must already be installed. The release workflow uses pinned uv version 0.10.0 to resolve and export the runtime dependency lock for the release; the lock is attached to the release so subsequent installs use the same resolved versions and hashes.

POSIX shell:

```sh
curl -fsSL https://raw.githubusercontent.com/Txdana/Peke/main/install.sh | sh
```

PowerShell:

```powershell
irm https://raw.githubusercontent.com/Txdana/Peke/main/install.ps1 | iex
```

Options: `--dry-run`, `--yes`, `--no-modify-path`, `--uninstall`; PowerShell equivalents are `-DryRun`, `-Yes`, `-NoModifyPath`, `-Uninstall`. `PEKE_VERSION` may be set to a published version such as `0.3.0` or `v0.3.0`. The default is the latest stable GitHub Release. The scripts intentionally fail if the release is missing the expected wheel, lock file, or manifest.

For a checkout or extracted source archive, Windows also supports `./install.ps1 -FromSource`. This keeps the same pipx-based installation approach but installs the current source tree (including bundled SearXNG) in editable mode with the GUI extra. Source mode resolves dependencies from the configured package index and does not use the release checksum lock; use the default mode for published, checksum-verified release assets.

## Integrity limitations

The checksum manifest and assets are delivered by the same GitHub Release. This detects corruption or mismatched assets, but does not independently authenticate the release against a compromised repository account or release pipeline. The lock covers runtime dependencies and hashes, but source builds can still require build-system dependencies; `llama-cpp-python` may need a compatible prebuilt wheel or a local C/C++ toolchain. The installer does not bootstrap Python or pipx.

The in-app `peke update` command remains a convenience wrapper around `pipx upgrade peke` and uses the configured package index; it does not use the release-specific lock. To update with the verified release artifacts, rerun the bootstrap script with `PEKE_VERSION` set to the target published version. Manual install from PyPI remains available:

```sh
pipx install 'peke[gui]'
peke doctor
peke launch
```

The manual PyPI command uses normal pip dependency resolution and does not consume the release's hash-locked requirements file. Uninstalling removes the pipx-managed application but intentionally retains Peke's user configuration. That configuration location is determined by `platformdirs`; `PEKE_HOME` is not used as an application setting directory.
