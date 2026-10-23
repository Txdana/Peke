# Release validation results for this development environment

Date: 2026-10-23

## Checks completed

- `pytest -q`: **79 passed, 4 skipped**. The skipped tests are GUI tests that
  require optional Qt dependencies unavailable in this environment.
- `python -m compileall -q src/peke scripts/validate_release.py`: passed.
- `sh -n install.sh`: passed.
- `sh install.sh --dry-run`: passed.
- `pyproject.toml` parsed with Python's TOML parser.
- `.github/workflows/ci.yml` and `.github/workflows/release.yml` parsed as YAML.
- Release-validator negative test correctly rejects a tag that does not match
  `project.version`.
- Source ZIP integrity checked after packaging.

## Release build blocker

A wheel and source distribution were **not** built in this environment. The
configured build backend `hatchling==1.27.0` is not installed or cached, and
package index access fails due unavailable DNS/network connectivity. Both
`uv build --offline` and an online `uv build` attempt therefore failed before
compilation/building began. This is an environment limitation, not a successful
release build.

The release workflow now builds and validates the wheel and source distribution
in GitHub Actions, checks that a pushed version tag matches `pyproject.toml`,
verifies required package contents, and validates release asset checksums. That
workflow still needs to run in the connected GitHub repository. No GitHub
Release or PyPI publication was created from this environment.

## Still required before calling a public release validated

1. Push this commit to the real repository.
2. Wait for CI and the release workflow to pass online, including security
   audits and the GUI offscreen test job.
3. Tag the release with the same version as `pyproject.toml` (currently
   `0.1.0`) and confirm the workflow creates the expected artifacts.
4. Inspect the published assets and run the installers on clean Windows and
   POSIX user accounts.
5. Perform actual GUI launch, local GGUF inference and live REA/browser tests
   on a machine with those optional components installed.
