# Phase 4 — Expanded tests and security checks

## Implemented

- Added regression coverage for unsafe target URL schemes, embedded URL credentials, invalid ports, control characters, backslash ambiguity, and explicitly permitted local development targets.
- Added request-header validation for invalid header names, CR/LF injection, excessive header counts, and oversized values.
- Added resource bounds for local inference and network fetch settings, including finite numeric checks and bounded fetch timeouts.
- Added a 50 MiB response-body limit before parsing response content.
- Redacted URL credentials and query values from Peke-generated URL logs and fetch errors.
- Changed user settings persistence to a unique temporary file plus atomic replacement, with owner-only file permissions and private directory permissions on POSIX systems.
- Tightened custom Pydantic schema checks to allow only a declarative schema subset before import. This is a guardrail, not a sandbox; untrusted schema files must not be loaded.
- Added regression tests that ensure application subprocess calls do not opt into `shell=True` and source does not call built-in `eval`/`exec`.
- Added Bandit static analysis and `pip-audit` dependency checks to CI and release test jobs.
- Set CI workflow default permissions to read-only repository contents; the release job separately requests write access only where needed.
- Expanded `SECURITY.md` with the trust model, known limitations and reporting guidance.

## Local validation

- `pytest -q`: **76 passed, 4 skipped**.
- `python -m compileall -q src tests`: passed.
- `sh -n install.sh`: passed.
- `pyproject.toml` parsed successfully.
- CI workflow YAML parsed successfully.

## Checks not executed in this environment

Bandit, Ruff, mypy and pip-audit were not installed in the execution environment, and this environment did not have package-network access for installing them. CI now installs and runs Bandit and pip-audit; Ruff and the focused mypy check remain part of the existing CI configuration. Their results must be confirmed from an actual CI run.

## Security scope and limitations

Peke is a local desktop tool, not a hardened multi-tenant URL-fetch service. User-selected loopback and private-network HTTP targets remain allowed by design for local development and authorized internal testing. This means Peke can reach whatever the current user can reach. Do not run it with elevated privileges, expose Chrome DevTools Protocol to the network, load untrusted schema files, or use untrusted model weights. Extracted files are not encrypted by Peke.
