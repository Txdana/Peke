# Changelog

All notable changes to Peke are documented here. This format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow Semantic Versioning.

## Unreleased

- Hardened the Windows source-build installer: fixed PowerShell native argument passing, improved Python/Git/Inno Setup discovery, checked command exit codes, verified the exact pinned commit, derived the installer version from `pyproject.toml`, and quoted custom install paths.
- Made PyInstaller fail fast when collection of required runtime packages fails instead of silently building a potentially incomplete GUI bundle.
- Updated Windows packaging checks and documentation to use the package version consistently.

- Bundled the SearXNG source and runtime dependencies for a private loopback-only local service on Windows x64; Docker is no longer required. Added a managed process lifecycle, JSON API readiness checks, per-user secret/settings, and AGPL source/licence notices.
- Hardened search URL/configuration validation, bounded pagination, skipped malformed result URLs, added regression tests, and patched SearXNG’s optional Valkey diagnostic import for native Windows compatibility.
- Corrected package/application version drift and aligned license statements with Apache-2.0.
- Added TOML-reader compatibility for Python 3.10 and retained a deprecated compatibility alias for earlier REA integrations.
- Hardened file-based credential fallback with private permissions, atomic writes, and symlink refusal.

- New `peke ask`: situation-aware research (SearXNG search, fallback to prompt links, relevance ranking, link-following, REA/subagent deep discovery, cited answers). See docs/ask.md.
- Added Probe and Schema subagents; deep discovery now fetches JS bundles and writes a reverse-engineered draft profile.
- Pipeline: `max_pages` now paginates (next link, `page`, `offset`/`limit`); JSON lists validate every item; Markdown output built with one dump per record.
- `REQUEST_DELAY_SECONDS` is now enforced per host; response, probe and script caps are configurable (`0` = unlimited); timeout and MCP caps raised.

## [0.2.0] - 2026-10-24

### Added
- **MCP Server ("Agent Access"):** Peke is now an MCP server for local AI agents (Claude Code, Claude Desktop, Codex, Cursor, Gemini CLI, VS Code, Windsurf).
- **11 MCP Tools (`peke_*`):** `peke_doctor`, `peke_fetch`, `peke_discover_endpoints`, `peke_probe_endpoint`, `peke_extract`, `peke_run_profile`, `peke_list_profiles`, `peke_get_profile`, `peke_save_profile`, `peke_schemas`, `peke_get_run`.
- **Resources & Prompts:** `peke://runs`, `peke://profiles/{name}`, `peke://schemas/{name}` and workflow prompts `peke_reverse_engineer`, `peke_extract_page`.
- **Security & SSRF Guard:** Strict IP checks against loopback, private, link-local, and cloud metadata ranges; secret redaction; loopback-only Streamable HTTP server with bearer token and Host/Origin validation.
- **GUI "Agent Access (MCP)" Pane:** Sidebar tab with server status, agent registration cards, policy settings, HTTP access, and live activity log monitoring.
- **Agent Registration CLI (`peke mcp`):** Automatic agent detection, plan/diff confirmation, backup, and registration.

## [0.1.0]

### Added
- Terminal startup banner with color-aware plain-text fallback.
- Optional frameless GUI splash and a persisted splash toggle.
- About dialog and packaging/release documentation.
- Maintainer guides, security policy, contribution guidance, and issue/PR templates.
- Release workflow for tagged source and wheel builds with gated PyPI trusted publishing.

### Changed
- GUI window title is now simply “Peke”.

### Added
- Added a maintainer release checklist and automated release-asset validation for wheel/sdist contents, tag/version consistency, and SHA-256 manifest integrity.

### Deferred
- Bundled upstream font binaries and their OFL texts still need to be added from their official sources.
- End-to-end release publishing and cross-platform startup performance require maintainer-run verification.

### Installer and packaging hardening (unreleased)
- Installers now download a published GitHub Release wheel and a release-specific hash-locked runtime requirements file, verify both against `SHA256SUMS`, and install dependencies with pip `--require-hashes`.
- Release CI uses pinned uv 0.10.0 to export the dependency lock, runs installer syntax/dry-run checks on Linux, macOS, and Windows, validates built distributions, smoke-installs the wheel without dependency resolution, and publishes checksum-protected assets.
- Source distributions explicitly include installer scripts and installation documentation.
- Third-party dependency resolution is still performed by pip from the configured package index. A hash-locked dependency bundle and pinned uv bootstrap remain future hardening work.
