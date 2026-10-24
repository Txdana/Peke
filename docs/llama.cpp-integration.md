# Standalone llama.cpp runtime integration

Peke uses `llama-server`, the OpenAI-compatible server built by the official llama.cpp project. The Python package does not import or build `llama-cpp-python` on the normal path. This avoids pip attempting to build the Python binding's vendored llama.cpp source tree on Windows, where deep source paths can fail during extraction/build.

## Configure an existing runtime on Windows

1. Obtain a trusted CPU-compatible `llama-server.exe` build from the official llama.cpp project, or build it from source using the steps below.
2. Put the executable in `%LOCALAPPDATA%\Peke\runtime\llama-server.exe`, or set `LLAMA_SERVER_PATH` to its full path.
3. Set `MODEL_PATH` to an existing `.gguf` model. Peke does not automatically download model weights during installation.
4. Open a new PowerShell window and run `peke ai status`, then `peke ai test`.

Peke searches `LLAMA_SERVER_PATH`, `PATH`, and its application-managed runtime directory. The server binds to `127.0.0.1` by default. Logs are written to `%USERPROFILE%\.peke\logs\llama-server.log`.

## Build from the supplied llama.cpp source archive

Extract `llama.cpp-master.zip` and run this from the Peke source directory in PowerShell:

```powershell
# Example assumes the source archive was extracted beside the Peke folder.
.scripts\build_llama_runtime.ps1 -SourceDir ..\llama_src\llama.cpp-master
```

The script configures a CPU-only Release build, builds the `llama-server` target, verifies `--version`, and copies the executable into `%LOCALAPPDATA%\Peke\runtime`. It requires CMake and a working C/C++ build toolchain. This is an explicit developer operation, not part of normal Peke installation. GPU builds require separate backend-specific configuration and compatible drivers; this script does not claim GPU acceleration.

## Install Peke from source

```powershell
.\install.ps1 -FromSource
```

This installs Peke and its Python/GUI dependencies only. It does not build llama.cpp, install `llama-cpp-python`, or download model weights. Peke's non-AI features remain available when the standalone runtime or model is not configured.

## Diagnostics

```powershell
peke hardware
peke ai recommend
peke ai status
peke ai test
```

The recommendation is a conservative heuristic, not a guarantee that a particular model fits or performs well. Test with the actual model and machine before relying on it.
