# Contributing to Peke

Thanks for helping improve Peke. Keep pull requests focused, tested, and compatible with Python 3.10–3.12.

## Development setup

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[gui,gpu,dev]"
scrapling install
ruff check .
pytest -q
QT_QPA_PLATFORM=offscreen pytest -q tests/gui
```

Set `MODEL_PATH` only to a local, compatible GGUF file if a test or manual run needs LLM extraction. Never commit `.env`, credentials, model weights, or collected private data. Tests should use fixtures and mocks rather than live websites or a real model.

## Pull requests

- Explain the user-visible change and why it is needed.
- List tests run and their results.
- State what is deliberately left for later phases.
- Include screenshots for GUI changes and update documentation/CHANGELOG.
- Keep changes small; add regression tests for bug fixes.
- Do not add telemetry or hidden network calls.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
