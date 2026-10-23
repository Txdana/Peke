# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-02-23

### Added
- **Terminal Banner & CLI Polish**: Added rich monospace ASCII banner in `src/peke/banner.py`, `--version`, `--no-banner`, `--no-splash` flags, and `peke doctor` diagnostic suite.
- **GUI Splash Screen**: Frameless dark splash screen with animated line-by-line reveal, background font/model loading, key/mouse dismiss, OS reduced motion support, and `QSettings` toggle.
- **App Identity & About Dialog**: Terracotta search-lens SVG icon asset, About dialog displaying license, version, third-party notices, and project links.
- **Security Enhancements**: Redaction of sensitive HTTP header values (`Authorization`, `Cookie`, `X-API-Key`) in logs and fetch results.
- **Documentation**: Comprehensive guides in `docs/` (`rea-workflow.md`, `profiles.md`, `schemas.md`, `models.md`, `architecture.md`), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, and updated `README.md`.
- **Packaging & Release**: PyInstaller spec file (`packaging/peke.spec`), PyPI release GitHub Action (`.github/workflows/release.yml`), and package asset inclusions in wheels.
