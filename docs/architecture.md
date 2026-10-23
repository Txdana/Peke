# Architecture

```text
CLI / PySide6 GUI
       │
       ▼
Profile + Settings ── optional REA subprocess (user-configured)
       │
       ▼
Scrapling fetcher ── FetchResult (raw HTML/text or JSON)
       │
       ├── clean JSON ──> Pydantic validation
       │
       └── deterministic parsing fails ──> llama-cpp-python
                                             │ constrained JSON output
                                             ▼
                                      Pydantic validation
       │
       ▼
PipelineResult ──> JSON / Markdown / GUI output
```

The `src/` layout keeps importable package code under `src/peke`. The CLI remains usable without the GUI extra. PySide6 is imported only for GUI launch. The GUI's worker object runs pipeline work in a `QThread` and emits events back to the UI thread. REA is optional and its output is treated as untrusted hints. No telemetry or background daemon is part of the design.

## Trust boundaries

- Target URLs, page bodies, endpoint hints, and model output are untrusted.
- Pydantic validation is the final data-shape check, not a guarantee that source data is truthful.
- Custom schema modules execute Python when imported and must be trusted.
- Header values, cookies, and secrets must not be written to logs or committed to source control.
