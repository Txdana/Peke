# Peke

**A local-first desktop workbench for turning permitted web responses into schema-validated JSON and Markdown.** Peke combines optional REA endpoint hints, Scrapling fetchers, deterministic parsing, and an in-process `llama.cpp` model. It does not require Ollama or a background daemon.

> **Project status:** community project / active development. The GUI is optional. The local model is optional for clean JSON endpoints but required when deterministic parsing fails and LLM extraction is needed.

## Install and quickstart

Install the CLI and optional desktop UI from a verified GitHub Release wheel with the user-level installer (requires Python 3.10+ and `pipx`):

```bash
curl -fsSL https://raw.githubusercontent.com/Txdana/Peke/main/install.sh | sh
peke doctor
peke launch
```

On Windows, run the PowerShell installer:

```powershell
irm https://raw.githubusercontent.com/Txdana/Peke/main/install.ps1 | iex
```

You can also install directly from PyPI with `pipx install 'peke[gui]'`. The bootstrap scripts verify the Peke wheel and a release-specific hash-locked runtime dependency list against the release `SHA256SUMS` manifest before installation. See [`docs/installers.md`](docs/installers.md) for options and integrity limitations.

Or develop from a checkout:

```bash
python -m pip install -e ".[gui,dev]"
scrapling install
peke validate profiles/example.yaml
peke run profiles/example.yaml -o out.json
```

For browser-based Scrapling fetchers, `scrapling install` installs the browser dependencies documented by Scrapling. It is an explicit setup step; Peke does not download browsers or models automatically. A GGUF model is only needed for LLM fallback. Set `MODEL_PATH` to a local compatible file if required.

## How the pipeline works

```text
Profile YAML ──> optional REA hints ──> Scrapling fetch
                                         │
                         ┌───────────────┴──────────────┐
                         ▼                              ▼
                 JSON parses cleanly              HTML / invalid JSON
                         │                              │
                         ▼                              ▼
                Pydantic validation              local llama.cpp
                         │                              │
                         └──────────────┬───────────────┘
                                        ▼
                              schema-validated records
                                        │
                                JSON / Markdown / GUI
```

REA is optional. Its findings are hints, not proof that an endpoint is safe, stable, public, or authorized for your use. Review findings and confirm request parameters before using them.

## Requirements

- Python 3.10–3.12 (CI-tested versions).
- For the GUI: PySide6 (`pipx install 'peke[gui]'`).
- For browser-based fetchers: run `scrapling install` after installing Peke.
- For LLM extraction: a compatible local GGUF model and enough RAM/VRAM for its size and context.
- For GPU memory telemetry: optional `nvidia-ml-py`; CPU RAM fallback uses optional `psutil`.

## Local AI Agent Integration (MCP Server)

Peke acts as a Model Context Protocol (MCP) server for local AI agents such as Claude Code, Claude Desktop, Codex, Cursor, Gemini CLI, VS Code, and Windsurf:

```bash
# Register Peke with your local AI agents
peke mcp install

# Test server readiness and stdio handshake
peke mcp doctor
```

Agents can use Peke's 11 tools to stealth-fetch pages, discover API endpoints, probe JSON shapes, and extract schema-valid data using local GGUF models. See [`docs/mcp.md`](docs/mcp.md) and [`docs/mcp-security.md`](docs/mcp-security.md) for details.

## CLI reference

- `peke` — show the terminal banner, then launch the GUI.
- `peke mcp serve` — run stdio or HTTP MCP server for AI agents.
- `peke mcp install` — register Peke with detected local AI agents.
- `peke mcp doctor` — test agent registrations and stdio handshake.
- `peke --no-banner` — launch without terminal branding.
- `peke --no-splash` — skip the GUI splash for this launch.
- `peke --version` — show the banner and version; combine with `--no-banner` for version only.
- `peke gui` — explicitly launch the GUI.
- `peke run PROFILE -o out.json [--format json|md] [--stealth|--basic] [--verbose]` — run a profile.
- `peke validate PROFILE` — validate a profile without fetching.
- `peke schemas` — list built-in schemas.
- `peke discover URL --out profiles/draft.yaml` — collect optional REA hints and write a draft profile.
- `peke doctor` — show dependency and configuration readiness.

The splash can also be disabled persistently from the GUI's **Startup splash** toggle. Set `PEKE_REDUCED_MOTION=1` to show its final frame without animation on systems where reduced-motion preferences are not exposed through Qt. If PySide6 is missing, the CLI prints `Install the GUI with: pipx install 'peke[gui]'` and exits with status 1.

## Configuration

Peke loads environment variables and `.env` for local development. GUI settings may also be saved in the platform's user configuration directory. Environment variables take precedence.

| Variable | Default | Purpose |
| --- | --- | --- |
| `MODEL_PATH` | unset | Path to a local GGUF model; needed only for LLM fallback |
| `N_CTX` | `8192` | Model context window |
| `N_GPU_LAYERS` | `0` | Number of layers to offload to GPU |
| `N_THREADS` | `0` | CPU threads; zero lets llama.cpp choose |
| `MAX_INPUT_CHARS` | `24000` | Maximum source text per extraction chunk |
| `TEMPERATURE` | `0.1` | Extraction temperature, clamped to 0.0–0.1 |
| `REQUEST_DELAY_SECONDS` | `1.0` | Minimum delay / rate-limit guard between runs or requests |
| `OUTPUT_DIR` | `output` | Default output directory |
| `REA_COMMAND` | unset | Installed REA CLI executable, usually `rea` |
| `REA_CDP_ENDPOINT` | `http://127.0.0.1:9222` | Loopback Chrome DevTools endpoint used by REA browser analysis |
| `FETCH_TIMEOUT` | `30` | Fetch timeout in seconds |

See [docs/profiles.md](docs/profiles.md), [docs/schemas.md](docs/schemas.md), [docs/models.md](docs/models.md), and [docs/architecture.md](docs/architecture.md) for details.

## FAQ and troubleshooting

**Do I need a model?** No for JSON that directly validates against the selected schema. If deterministic parsing fails, configure `MODEL_PATH` to a local GGUF model.

**Why does `pipx install 'peke[gui]'` fail while building llama-cpp-python?** `llama-cpp-python` may compile native code when a compatible wheel is unavailable. Update pip/build tools, install the platform's C/C++ build toolchain, and consult the upstream llama-cpp-python installation guide. Peke does not bundle native binaries or weights.

**Why is GPU offload not working?** CPU mode (`N_GPU_LAYERS=0`) is the portable default. GPU acceleration requires a llama-cpp-python build matching your supported backend and driver. Increase layers gradually and leave memory headroom for the context cache.

**Why does the stealth fetcher fail?** Run `scrapling install` and check the upstream Scrapling install documentation for supported browsers and system libraries. Basic fetch mode may be more appropriate for simple public APIs.

**Why is REA CLI Off shown?** Peke could not find the executable configured by `REA_COMMAND`. REA is optional; all other pipeline functionality should remain available. To inspect a website, open it in a Chrome-family browser started with a loopback remote-debugging endpoint and configure `REA_CDP_ENDPOINT`.

**Can I load a custom schema?** Yes, use `path/to/schema.py:ModelName`. Python schema modules execute code when imported; only load files you wrote or audited.

## Roadmap

- [x] Headless core pipeline and CLI
- [x] PySide6 workbench shell
- [x] Live endpoint, output, and metrics components
- [x] Startup polish, docs, and release workflow preparation
- [ ] Maintainer-verified cross-platform release and screenshots
- [ ] Future improvements based on issues and community feedback

## Responsible use

Use Peke only for systems and data you are authorized to access. Respect `robots.txt`, site terms, privacy and data-protection rules, rate limits, and server capacity. Obtain permission where required. Do not use Peke to circumvent authentication, paywalls, CAPTCHAs, access controls, or other restrictions to collect data you are not permitted to collect. Stealth fetching is not authorization. Treat REA findings as untrusted hints and review them before use. Avoid sending secrets or private data to targets, and redact headers/cookies from logs and bug reports.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [SECURITY.md](SECURITY.md). Peke is distributed under the MIT License; see [LICENSE](LICENSE). Third-party components retain their own licenses; see [docs/third-party-notices.md](docs/third-party-notices.md).


## First-run setup

Run `peke setup` to save a local GGUF model path and basic runtime settings in
the per-user config file. `peke launch` opens the GUI and starts setup if no
user config exists. Peke never downloads model weights automatically. Use
`peke update` / `peke uninstall` for pipx-managed installs; uninstall retains
your per-user settings and model files.

## Security and provider scope

Peke's supported extraction provider is the in-process local `llama-cpp-python`
runtime. It does not send page content to hosted LLM providers and has no
telemetry. Custom schema Python files can execute code when imported; only load
schema files you trust. REA static findings must be reviewed and are always
unverified until you inspect them. Peke does not automatically send mutating
requests to discovered endpoints.

The bootstrap scripts verify the published release wheel and the release-specific
hash-locked runtime dependency list before installing with pipx. The release
manifest is delivered by the same GitHub Release and is not independently
signed; source builds may also require build-system dependencies or a local
compiler. Review [`docs/installers.md`](docs/installers.md) before using them in
managed environments.


## Release process

Maintainers should follow [`docs/release.md`](docs/release.md). Tagged releases
are built and validated by GitHub Actions; do not treat a local test run as a
validated published release.
