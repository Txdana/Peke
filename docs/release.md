# Release checklist

This is the maintainer procedure for producing and validating a Peke release.
A green local test run is not equivalent to a successful release build, and a
successful CI build is not evidence that a GitHub release has been published.

## Before tagging

1. Update `project.version` in `pyproject.toml` to the intended `X.Y.Z` version.
2. Move the intended changes from `CHANGELOG.md`'s `[Unreleased]` section into
   a versioned section and add a fresh `[Unreleased]` section.
3. Review `README.md`, supported Python versions, third-party notices, and
   installer instructions.
4. Confirm screenshots are real and reviewed before replacing the current
   screenshot placeholders.
5. Run `pytest -q`, `ruff check .`, `mypy src/peke/banner.py`, `bandit -q -r
   src/peke -ll`, and `pip-audit --strict --skip-editable` in an environment
   with the project's optional tooling installed.

## Build and validate

The release workflow is the authoritative release build because this checkout
may not have the build backend, compiler, GUI libraries, or package index access
needed to reproduce the full build locally.

1. Push the reviewed commit and wait for CI to pass.
2. Create a tag matching `pyproject.toml`, for example `v0.1.0` for version
   `0.1.0`, and push it.
3. The release workflow tests supported Python versions, runs the GUI test job,
   checks installer syntax on Linux/macOS/Windows, builds wheel and sdist,
   validates metadata, smoke-installs the wheel, exports hash-locked runtime
   requirements, and creates a `SHA256SUMS` manifest.
4. The `scripts/validate_release.py` step checks that distribution metadata,
   required files, tag/version, release assets and SHA-256 manifest agree.
5. Inspect the workflow's uploaded `python-distributions` and
   `github-release-assets` artifacts before treating the release as validated.
6. For tagged builds, confirm the GitHub Release contains exactly one Peke
   wheel, one source archive, `requirements-hashed.txt`, and `SHA256SUMS`.
7. Confirm PyPI publishing only if trusted publishing is configured and the
   `PYPI_TRUSTED_PUBLISHING_ENABLED` repository variable is `true`.

## After publication

- Test the published installer in a clean, disposable user account on Windows
  and at least one POSIX platform.
- Run `peke doctor`, launch the GUI, and verify that the model remains optional
  until LLM fallback is requested.
- For local inference, use a separately obtained compatible GGUF file; do not
  commit model weights or credentials to the repository.
- Verify that uninstall removes the pipx app but preserves user configuration.
- Record the tag, release URL, CI run, artifact hashes, and any platform-specific
  limitations in the release notes.

## What the workflow does not prove

The release workflow does not publish a release until a matching tag is pushed.
A successful wheel smoke test checks importable package resources and entry
points; it does not prove full GUI startup, real GGUF inference, REA/browser
integration, or a clean-machine installer run. Those require dedicated runtime
checks on real supported systems. The release checksum manifest is delivered
with the same release assets and is not an independent signature.
