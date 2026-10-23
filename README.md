# Peke

> Open-source desktop workbench that chains **REA**, **Scrapling**, and **llama.cpp** into a unified, privacy-first data-extraction pipeline.

```
┌──────────────────────────────────────────────────────┐
│  PEKE  [MCP Active]                local: llama.cpp  │
└──────────────────────────────────────────────────────┘
  │
  ├── [01] REA Analysis  ──▶  Discovered Endpoint
  ├── [02] Scrapling     ──▶  Cloudflare Bypassed
  └── [03] Local SLM     ──▶  Clean JSON Formatted
```

## Quickstart

### 3-Command Installation
```bash
pipx install 'peke[gui]'
peke doctor
peke
```

## Pipeline Overview

```
 [ Target Web App ]
         │
         ▼
 ┌───────────────┐
 │  1. REA MCP   │  ──▶ Reverse-engineers hidden endpoints & headers (Optional)
 └───────┬───────┘
         │ (Profile YAML)
         ▼
 ┌───────────────┐
 │ 2. Scrapling  │  ──▶ Stealth fetching & Cloudflare bypass
 └───────┬───────┘
         │ (HTML / JSON Payload)
         ▼
 ┌───────────────┐
 │ 3. llama.cpp  │  ──▶ In-process GGUF LLM turns raw payloads into Pydantic JSON
 └───────────────┘
```

## Requirements
- Python 3.10+
- PySide6 (for GUI)
- Local GGUF quantized model (set via `MODEL_PATH`)

## Configuration Table

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| `MODEL_PATH` | Path to local GGUF llama.cpp model file | Required for LLM fallback |
| `LLM_TEMPERATURE` | Temperature setting for LLM inference (clamped 0.0 - 0.1) | `0.0` |
| `REA_SERVER_URL` | Endpoint URL for REA MCP server | `http://localhost:8000` |

## Documentation

- [REA Workflow](docs/rea-workflow.md) - Transitioning REA findings into target profiles
- [Target Profiles Reference](docs/profiles.md) - Full YAML profile field specification
- [Custom Schemas](docs/schemas.md) - Defining and registering Pydantic schemas
- [Model Selection](docs/models.md) - Choosing GGUF models and RAM/VRAM planning
- [Architecture](docs/architecture.md) - Core system design and component interaction

## FAQ & Troubleshooting

### llama-cpp-python Build Issues
If `llama-cpp-python` fails to compile during installation, ensure C/C++ compiler tools (`gcc`, `g++`, `cmake`) are installed. For CUDA GPU acceleration:
```bash
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python
```

### Scrapling Browser Installation
If `StealthyFetcher` requires browser engines:
```bash
scrapling install
```

## Responsible Use & Ethics

Peke is designed for authorized data collection, web analysis, and software integration. Users are strictly expected to:
- Respect target website `robots.txt` rules and Terms of Service (ToS).
- Observe request rate limits and prevent denial-of-service conditions.
- Collect data only with proper authorization.
- Never circumvent access controls for data you are not permitted to access.

## Roadmap
- Multi-target profile batch processing
- Automated schema generation from sample payloads
- Dynamic profile exports to Python code snippets

## License
[MIT License](LICENSE)
