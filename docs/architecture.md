# Peke Architecture & Data Flow

Peke is an open-source desktop extraction workbench written in Python 3.10+ using PySide6 for GUI controls, Scrapling for stealth HTTP operations, and `llama-cpp-python` for local LLM extraction.

## High-Level Architecture Diagram

```
 ┌─────────────────────────────────────────────────────────────┐
 │                         Peke GUI                            │
 │ (PySide6 / MainWindow / Workspace / EndpointTree / JSONView)│
 └──────────────────────────────┬──────────────────────────────┘
                                │ Calls
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                   Peke Pipeline Engine                      │
 │                 (peke.pipeline.Pipeline)                    │
 └───────┬──────────────────────┬──────────────────────┬───────┘
         │                      │                      │
         ▼                      ▼                      ▼
 ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
 │ peke.discover │      │  peke.fetch   │      │ peke.extract  │
 │  (REA MCP)    │      │  (Scrapling)  │      │  (llama.cpp)  │
 └───────────────┘      └───────────────┘      └───────────────┘
```

## Component Breakdown

1. **`peke.config`**: Loads environment settings (`MODEL_PATH`, `LLM_TEMPERATURE`, `REA_SERVER_URL`).
2. **`peke.profile`**: Defines and loads target profiles (`TargetProfile`) from dicts or YAML files.
3. **`peke.discover`**: Connects to optional REA reverse-engineering MCP server or CLI to generate endpoint hints.
4. **`peke.fetch`**: Wraps Scrapling `Fetcher` and `StealthyFetcher` for request dispatch and Cloudflare bypass.
5. **`peke.extract`**: Validates clean JSON payloads directly with Pydantic; invokes local `llama.cpp` model with JSON schema constraints when deterministic parsing fails.
6. **`peke.gui`**: PySide6 dark-themed interface, asynchronous worker threads (`PipelineWorkerThread`), and live metrics telemetry.
