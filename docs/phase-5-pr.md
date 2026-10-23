# Phase 5: user-level installer and first-run setup

## Summary
- Added `peke setup` to select an existing local GGUF and save runtime preferences to per-user settings.
- Added `peke launch`, `peke update`, and `peke uninstall` CLI commands.
- Added POSIX shell and Windows PowerShell pipx bootstrap helpers with dry-run and uninstall paths.
- Added installer documentation and tests for the bootstrap scripts.
- Fixed `--version` output so the version is plain text without Rich highlighting.

## Deliberately left for later
- The installer scripts do not yet download a pinned `uv` binary or verify its SHA-256 against a committed platform checksum table.
- They do not yet install from a release wheel bundle with a hash-locked requirements file.
- Full Linux/macOS/Windows clean-machine integration tests, shellcheck, and Pester tests require CI infrastructure.
- The first-run setup accepts an existing local model or skips it; it does not download model weights automatically.
- Hosted LLM providers are not implemented; Peke remains local-first.

## Verification
- `pytest -q`: 28 passed, 3 skipped (GUI dependencies unavailable in this environment).
- Python compilation: run before merge.
- Ruff, mypy, wheel build, and pipx install must be run in CI before merge.
