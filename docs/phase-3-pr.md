# Phase 3: live data, REA integration, settings pages

## Summary
- Added optional REA JSON-stdout adapter with timeout, stderr capture, normalization, and fallback warnings.
- Added `peke discover URL --out ... [--findings ...]` draft-profile generation.
- Extended endpoint hints with size, parameters, headers, and hidden-state metadata; endpoint tree groups host/path and offers endpoint selection.
- Added JSON syntax highlighting, line numbers, search, large-output preview, Markdown copy, expanded metrics, and a dependency-free throughput sparkline.
- Added console filters, bounded logs, copy/save, optional GPU/CPU memory telemetry, scraper/model/schema settings pages, and user-config persistence.
- Added recorded REA fixture tests and schema-source safety checks.

## Deliberately left for later
- The adapter now follows REA's documented CLI flow (`list-browser-targets` → `analyze-web-bundle`) and parses the Evidence envelope. A fake CLI test covers command behavior; live browser verification still requires an installed REA CLI and a CDP-enabled browser.
- Cancellation cannot interrupt a currently executing Scrapling request or an in-flight llama.cpp generation call; cancellation is reported at stage boundaries.
- Font binaries and OFL licenses were not bundled because the environment had no verified font source files. System-font fallback remains enabled.
- GUI screenshots and the full offscreen GUI suite need to be generated/run in an environment with PySide6 and pytest-qt installed.

## Validation performed
- `python -m compileall -q src tests`
- `pytest -q` — 19 passed, 2 skipped in the available environment.
- Ruff and PySide6-based GUI tests could not be run in this environment.
