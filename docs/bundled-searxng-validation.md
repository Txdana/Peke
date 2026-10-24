# Bundled SearXNG implementation and validation record

## Target

- Windows x64.
- Keep Peke's existing user-level `pipx` installation approach.
- Bundle SearXNG source and Python dependencies in the Peke distribution.
- Run the service locally at `127.0.0.1:8888`; no Docker installation.
- External internet is required for upstream search-engine results.

## Implemented

- Included the supplied SearXNG source package, templates, static assets, translations, data files, and version metadata in `src/searx/`.
- Preserved the exact supplied upstream source archive in `vendor/searxng-master-source-archive.zip` and its upstream requirements/licence.
- Added SearXNG runtime requirements to the Peke project dependency list so the existing release lock captures them.
- Replaced the Docker controller with a managed `python -m searx.webapp` child process, loopback-only settings, generated per-user secret, JSON output, startup health checks, bounded logs, actionable failure logs, stop behavior, and normal-exit cleanup.
- Forces `SEARXNG_BIND_ADDRESS`, `SEARXNG_PORT`, and public-instance settings for the local process so inherited shell environment variables cannot expose it on the LAN.
- Patched the upstream optional Valkey error diagnostic so importing the SearXNG app does not require Unix-only `pwd` on native Windows.
- Kept the normal checksum-verified release installer and added `install.ps1 -FromSource` to install the current extracted source tree with the existing pipx method.
- Added packaging validation requirements for SearXNG modules, resources, licence files, and source archive.

## Checks performed in the build environment

- Python compilation of `src/peke`, `src/searx`, and release scripts: passed.
- Focused SearXNG, installer, release-validator, and packaging tests: 35 passed (one CLI test excluded because the environment does not have the `mcp` dependency installed).
- Additional configuration, fetch, profile, pipeline, schema, security, updater, extraction, and discovery tests: 49 passed.
- Project TOML parses and all 17 direct requirements from the supplied SearXNG `requirements.txt` appear as exact dependency pins.
- Full test collection is blocked by missing environment packages: `PySide6` and `mcp` (15 collection errors, 5 skipped tests).
- A wheel build could not be completed here because `hatchling==1.27.0` is not installed and package-index network access is unavailable. A live SearXNG process and Windows x64 smoke test were therefore not possible in this environment.

## Required release smoke test

On a Windows x64 machine with internet access, install from source with `./install.ps1 -FromSource` (or use the default checksum-verified published release after publishing the new wheel). Open Search & Research, start bundled SearXNG, confirm the JSON endpoint returns a `results` list, perform a real search, stop the service, and verify that the listener is gone. A source-code test pass is not a substitute for this real Windows runtime check.
