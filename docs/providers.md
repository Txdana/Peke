# AI Model Providers in Peke 0.3.0

Peke supports pluggable AI providers for schema-constrained extraction and sub-agent reconnaissance.

## Supported Providers

### 1. Local llama.cpp (Built-in)
- **Kind:** `local_builtin` / `local_custom_path`
- Uses the standalone `llama-server` executable through its OpenAI-compatible local API. This avoids requiring native Python binding compilation during normal installation.
- Shared model file locking ensures process-safe access across CLI, GUI, and MCP calls. Set `LLAMA_SERVER_PATH` or place `llama-server` on `PATH`; see `docs/models.md`.

### 2. Ollama
- **Kind:** `ollama`
- Default base URL: `http://127.0.0.1:11434`
- Connects to an existing local Ollama server instance.

### 3. OpenRouter
- **Kind:** `openrouter`
- OpenAI-compatible cloud provider API with searchable model catalog and pricing per M tokens.
- API keys are stored securely using OS keyring or restricted permissions fallback (`~/.peke/secrets.toml`).

### 4. Custom OpenAI-Compatible
- **Kind:** `custom_openai`
- Connects to self-hosted or cloud OpenAI-compatible endpoints (vLLM, LM Studio, LocalAI, Modal, RunPod).

## Configuration

Set provider preferences in `settings.json`, `config.toml`, or environment variables (`PROVIDER_MAIN_KIND`, etc.).
