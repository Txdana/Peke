# Phase 2: GUI shell + theme

## Summary

- Add optional PySide6 GUI launch through `peke` with no arguments and `peke gui`.
- Add the three-pane window, collapsible navigation, phase-two placeholder pages, themed endpoint table, event console, output tabs, export/copy actions, and QThread-backed pipeline worker.
- Add shared palette constants, runtime QSS token replacement, font registration with system fallback, and an offscreen GUI test job.
- Keep the CLI subcommands and headless pipeline available without importing GUI modules unless the GUI is requested.

## Deliberately left for later phases

- Live endpoint discovery/tree updates, JSON syntax highlighting, and dynamic GPU/VRAM telemetry.
- GUI profile-file picker and richer cancellation of an in-flight blocking fetch.

## Environment limitations before merge

- Upstream DM Sans, Fraunces, and IBM Plex Mono font binaries and their OFL files could not be fetched in the network-restricted build environment. The app registers them if installed in `gui/assets/fonts/` and falls back to system fonts. Add the licensed upstream files before claiming that the wheel bundles them.
- PySide6 and pytest-qt were unavailable locally, so GUI tests were collected as skipped; the offscreen CI job is configured to run them in a dependency-enabled environment.
- No GitHub remote/repository credentials were available in this workspace, so this document is PR-ready text, not a claim that a PR was opened.
