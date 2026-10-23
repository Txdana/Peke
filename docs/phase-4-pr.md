# Phase 4: splash, docs, packaging and release

## Summary

- Added a Rich terminal banner with an MCP availability hint and plain-text fallback for non-TTY/`NO_COLOR` output.
- Added `--no-banner`, `--no-splash`, a line-reveal splash screen, persistent splash preference, SVG app icon, and About dialog.
- Expanded the README and added architecture, profiles, schemas, models, REA workflow, third-party notices, contribution, conduct, and security documentation.
- Added issue/PR templates, changelog, and a tag-based release workflow with PyPI trusted publishing disabled until the maintainer sets `PYPI_TRUSTED_PUBLISHING_ENABLED=true` and configures the PyPI trusted publisher.
- Added banner regression tests and wheel asset verification to release CI.

## Deliberately left for later / maintainer verification

- Font binaries and OFL texts are not bundled because they were unavailable in the supplied repository; system font fallbacks remain enabled. Add upstream font files and licenses before claiming they are bundled.
- No PyInstaller builds are enabled; standalone packaging remains out of scope.
- The GUI splash does not load or download model weights. Model loading remains lazy to avoid slow startup and hidden resource use.
- Accessibility contrast review, keyboard-only walkthrough, sub-3-second startup measurement, stress testing, complete type checking, clean-environment pipx installation, and the release dry-run require a provisioned GUI/build environment.
- GitHub PR creation and screenshots require maintainer repository access and a display-capable environment.

## Validation performed

List exact local commands and results before merging. Do not mark the release ready until CI, clean-environment install, wheel-content checks, and GUI smoke tests pass.
