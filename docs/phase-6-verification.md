# Phase 6 — GUI, local model, and REA integration verification

## Implemented in this revision

- Replaced the speculative REA JSON-stdout subprocess contract with REA's documented CLI flow: `list-browser-targets <loopback-CDP-endpoint> --json`, followed by `analyze-web-bundle <endpoint> <target_id> --json`.
- Target selection prefers an exact URL match and rejects ambiguous matches. Peke does not launch, navigate, or control the browser.
- Parsed the REA Evidence envelope's `normalized_result.observations.endpoints`, retaining route-like endpoint candidates and evidence confidence/mechanism notes.
- Restricted REA CDP configuration to literal loopback IP endpoints with explicit ports; remote debugging endpoints are rejected.
- Unified CLI, GUI, and configuration reads/writes onto the same platformdirs settings path, fixed invalid JSON newline writing, and preserved settings when one settings page saves its values.
- Added REA CLI/CDP endpoint fields to the model settings page, surfaced local model load failures in the GUI console, and changed misleading static “MCP active” / “Cloudflare bypassed” status claims.
- Added deterministic tests for the local model adapter, user settings persistence, official REA CLI command order, target matching, Evidence parsing, timeout handling, invalid CDP endpoints, and ambiguous target rejection.

## Automated checks in this environment

- `pytest -q`: **44 passed, 4 skipped**.
- `python -m compileall -q src tests`: passed.
- `sh -n install.sh`: passed.
- The model tests use a fake `llama_cpp.Llama` runtime and fixture `.gguf` files; they verify lazy loading, constructor options, generation parsing and error behavior without downloading or bundling model weights.
- The REA tests use a fake local CLI that implements the documented command/output boundary. They verify Peke's adapter behavior without accessing a real website or browser.

## Checks that could not be run here

This environment does not have PySide6, pytest-qt, llama-cpp-python, Scrapling, Ruff, mypy, or the REA CLI installed. There is no real GGUF model configured and no active Chrome DevTools debugging session. The four GUI test modules were therefore skipped by pytest. The CI workflow already contains an offscreen Qt job that installs `.[gui,dev]`; that job must pass before treating GUI runtime verification as complete. A real model must be loaded on the intended machine, and a live REA/Chrome CDP run must be performed there as well.

The available Node.js version is 22.16.0, below the current upstream REA documentation's minimum Node 22.x patch level (22.19.0), so installing or running the official REA package in this environment would not be a valid upstream runtime test.

## Live verification on the target machine

1. Install the optional GUI and development test dependencies, then run `pytest -q tests/gui` with `QT_QPA_PLATFORM=offscreen`.
2. Install REA following its [official CLI guide](https://github.com/morluto/rea/blob/main/docs/cli.md). Use a supported Node.js version and configure `REA_COMMAND=rea`.
3. Start a dedicated Chrome-family browser with a loopback debugging endpoint, for example `google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/peke-rea-profile http://127.0.0.1:3000/`.
4. Set `REA_CDP_ENDPOINT=http://127.0.0.1:9222`, open the authorized target URL in that browser, then run `peke doctor` and `peke discover <target-url> --out profiles/discovered.yaml`.
5. Configure `MODEL_PATH` to a real compatible local `.gguf` file and run a profile that requires LLM fallback. Verify successful model loading, valid JSON output, and graceful failure when the path or runtime is invalid.

REA documentation: [CLI and Evidence](https://github.com/morluto/rea/blob/main/docs/cli.md), [Website observation with CDP](https://github.com/morluto/rea/blob/main/docs/browser-observation.md), and [MCP runtime contracts](https://github.com/morluto/rea/blob/main/docs/mcp-contracts.md).
