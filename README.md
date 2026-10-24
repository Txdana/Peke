# Peke

Peke is a local-first Windows desktop workbench for extracting structured data from web pages and local sources. It combines a PySide6 GUI, reusable YAML profiles, deterministic parsing, Pydantic schema validation, optional local GGUF inference through a standalone `llama-server`, local search through a bundled SearXNG runtime, and automation/MCP integrations.

> **Bring your own model.** Peke does not download model weights automatically. On first launch, open **Model Settings** and browse to a `.gguf` file you already have, if you want local-model extraction. The application can be opened and explored without configuring a model.

## Features

- Desktop workflows for targets, profiles, models, schemas, search, providers, subagents, MCP, and output.
- YAML profiles for repeatable extraction configuration.
- Web fetching and deterministic extraction with schema validation.
- Optional local GGUF inference through a separate `llama-server` process.
- Bundled SearXNG integration for local search without requiring Docker for the intended Windows package.
- JSON and Markdown output, pipeline events, and actionable errors.
- CLI, MCP, and automation interfaces for advanced workflows.

Optional integrations may require separately installed software or explicit configuration. See `docs/` for component details and limitations.

## Installation

### Windows one-command desktop installation (source build)

Open PowerShell and run:

```powershell
irm https://raw.githubusercontent.com/Txdana/Peke/main/install.ps1 | iex
```

This command builds the Windows application on your computer and installs it as if you had run a normal setup `.exe`. **The repository does not contain or host a prebuilt Peke installer executable.** The script fetches a pinned source revision, verifies the Git commit, prepares an isolated Python environment, packages the GUI with PyInstaller in windowed mode, compiles a temporary Inno Setup installer locally, runs that installer, and launches Peke. The generated setup executable lives only in the temporary build directory and is removed after installation. No model weights are downloaded.

If Git for Windows, Python 3.11/3.12 x64, or Inno Setup 6 is missing, the script attempts to install the build prerequisite with `winget`. Windows App Installer/`winget` must be available. Some prerequisite installers may request Windows permission to install software. The app itself installs per-user under `%LOCALAPPDATA%\Programs\Peke`; the setup creates a Start menu shortcut, offers an optional desktop shortcut, and registers an uninstaller.

**Release pin required:** `install.ps1` must contain a full 40-character SHA for a reviewed source commit. A real install refuses to run if the pin is missing or invalid; it never builds from the moving `main` branch. Since the one-line command fetches the script from `main`, maintainers should first commit the desktop changes, then commit the installer with its pin set to that reviewed source commit. Do not replace the pin with a branch name or short hash.

For a dry run, run a downloaded local copy with `-DryRun`; it reports the plan without installing prerequisites or changing the system. For development, `-NoLaunch` builds the setup executable and saves it as `Peke-Setup-0.3.0-x64.exe` in the current directory without installing it. `-NoBootstrap` disables automatic prerequisite installation and is intended for CI or controlled developer environments.

### Developer source setup

Prerequisites: Python 3.10–3.12, Git, and Windows build tools as applicable.

```powershell
git clone https://github.com/Txdana/Peke.git
Set-Location Peke
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[gui,dev]"
python -c "from peke.gui.app import run_gui; raise SystemExit(run_gui())"
```

If the GUI module entry point is unavailable in your checkout, launch the GUI through `python -c "from peke.gui.app import run_gui; raise SystemExit(run_gui())"`.

### CLI / other platforms

The CLI entry point is `peke`. The GUI is optional and requires the `gui` extra. Linux/macOS packaging is not equivalent to the Windows Inno Setup workflow. Refer to [`docs/installers.md`](docs/installers.md) before using platform-specific installers.

## First launch and model setup

1. Launch **Peke** from the Start menu or the installed executable.
2. Explore the application. No model is downloaded or required to open the GUI.
3. If you want local inference, open **Model Settings** and browse to your own `.gguf` model.
4. Configure the optional `llama-server` executable if it is not available through `PATH` or Peke's managed runtime location.
5. Use a profile or create one for the target and output schema you need.

Model weights are user-provided files and are not bundled in the installer. Review model licensing and provenance before use.

## Architecture

```text
PySide6 GUI / CLI / MCP
          |
          v
Settings + YAML profiles
          |
          v
Scrapling fetchers -> normalized fetch result
          |
          +--> deterministic parsing --> Pydantic validation
          |
          +--> optional local llama-server --> constrained output --> validation
          |
          v
Pipeline result -> GUI / JSON / Markdown
```

- `src/peke/` contains application logic, GUI, configuration, extraction, integrations, and CLI.
- `src/searx/` contains the bundled SearXNG source/runtime integration.
- `packaging/windows/Peke.spec` defines the PyInstaller GUI bundle.
- `packaging/windows/Peke.iss` defines the Windows installer, shortcuts, and uninstall registration.
- `install.ps1` is the source-build installer entry point; it creates the setup executable locally instead of downloading or committing one.
- `tests/` contains unit and integration tests; `.github/workflows/windows.yml` validates Windows packaging in CI.

The GUI's long-running work should be moved off the UI thread. `llama-server` is launched as a subprocess with argument arrays and is expected to bind to loopback by default. See [`docs/architecture.md`](docs/architecture.md).

## Configuration and data locations

Peke reads settings through its configuration module and supports environment variables for integration-specific overrides. Use the in-app Settings pages where available. The `MODEL_PATH` setting identifies the selected local model; `LLAMA_SERVER_PATH` can identify the `llama-server` executable. Consult `.env.example`, `docs/models.md`, `docs/providers.md`, and `docs/profiles.md` for supported options.

User data is stored in platform-appropriate application directories via `platformdirs`. Keep secrets in local environment/configuration or a supported credential store; do not commit them. Profiles can be stored as YAML and should be reviewed before sharing.

## Security and privacy

- No model weights are downloaded during onboarding.
- Network fetches contact the target sites and any explicitly configured integrations; local search uses the bundled SearXNG service.
- Web content, endpoint hints, profile inputs, and model output are untrusted. Validate results before using them in consequential workflows.
- Custom Python schema modules execute code and should only be loaded from trusted sources.
- Do not store tokens, cookies, passwords, or private data in source control or logs.
- Keep local model services bound to loopback unless you understand the network exposure.
- The installer must use a full pinned Git commit and verify the resulting `HEAD` before building. It fails closed when the pin is not configured.
- The one-command source-build path generates build artifacts locally; do not commit generated `.exe` installers or build directories. If a separate release pipeline later publishes binaries, generate them from reviewed source and publish checksums.
- Report security issues privately as described in [`SECURITY.md`](SECURITY.md).

Peke is a data extraction tool, not a guarantee that a source page or extracted value is accurate or safe.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[gui,dev]"
python -m pytest
python -m ruff check src tests scripts
```

The GUI uses PySide6. Tests should not require downloading model weights. Use temporary directories and mocks for tests that touch settings, external processes, network services, or the Windows registry.

## Build the Windows desktop app

On Windows x64 with Python 3.11 or 3.12 and Inno Setup 6 available, build the GUI and setup executable from the repository root:

```powershell
python -m pip install -e ".[gui]" pyinstaller==6.16.0
python -m PyInstaller packaging/windows/Peke.spec --clean --noconfirm
& "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe" /DAppVersion=0.3.0 packaging/windows/Peke.iss
```

PyInstaller uses `console=False` and the application icon. The output directory is `dist/Peke/`; the setup executable is written to `dist-installer/`. These are generated build outputs and must not be committed. The one-line consumer installer compiles the same Inno Setup script and runs the generated setup automatically.

## Tests and release process

Run tests with `python -m pytest`. Windows CI performs dependency installation, unit tests, packaging validation, PyInstaller build checks, and an installer dry-run. GUI startup smoke checks should run on a Windows worker with a Qt-capable desktop session; headless workers may need an offscreen Qt platform for noninteractive checks.

Before release:

1. Review and merge changes on the default branch.
2. Update `PinnedCommit` in `install.ps1` to the full SHA of the reviewed source revision to build. The installer script itself is fetched from `main`, so the pin should normally refer to the preceding source commit rather than trying to self-reference the commit that contains the pin.
3. Ensure the pinned source commit is available from GitHub and that the source-build dry-run passes.
4. Build the application and Inno Setup package on Windows x64.
5. Test install, launch, shortcuts, upgrade, and uninstall on a clean Windows account.
6. Keep generated EXEs out of the source repository. If a separately managed release channel publishes an installer, generate `SHA256SUMS` for that release asset.

The `irm ... | iex` command fetches only the PowerShell build script from `main`. That script builds the GUI and a temporary Inno Setup installer on the user’s machine; it independently pins and verifies the source revision it builds. Therefore, the script and its source pin must be committed to GitHub before the command can use the new workflow.

## Troubleshooting

- **Installer refuses to run because the pin is invalid:** the release maintainer has not set `PinnedCommit` to the full SHA for a released source revision.
- **winget unavailable:** install Windows App Installer, or install Git, Python 3.11/3.12 x64, and Inno Setup 6 manually before retrying.
- **GUI fails to start:** try launching from the installed executable, check the Windows event logs, and run the test suite against the same source revision.
- **Model is unavailable:** verify the `.gguf` path in Model Settings and check the `llama-server` configuration. Peke does not download models for you.
- **Local search fails:** consult `docs/searxng.md` and the bundled SearXNG validation notes.

## Project map

- `src/peke/` — core application, GUI, CLI, configuration, extraction, integrations.
- `src/searx/` — bundled SearXNG code and assets.
- `tests/` — automated tests.
- `docs/` — architecture, models, providers, security, installers, and release notes.
- `packaging/windows/` — PyInstaller spec and Inno Setup script.
- `scripts/` — release validation and runtime build helpers.
- `.github/workflows/` — continuous integration.

## License and acknowledgements

Peke is licensed under Apache-2.0. Third-party components retain their own licenses; see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), [`NOTICE`](NOTICE), and `licenses/`.
