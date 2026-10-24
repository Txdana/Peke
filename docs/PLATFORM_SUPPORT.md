# Peke Platform Support & Installation Guide

This document outlines official platform compatibility, system prerequisites, installation methods, and operating instructions for **Peke** on Linux, macOS, and Windows.

---

## Supported Platform Matrix

| Operating System | Supported Versions | Architectures | Python Versions | GUI Status | Local SearXNG |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Linux** | Ubuntu 22.04 LTS, 24.04 LTS (Debian/Fedora compatible) | `x86_64`, `aarch64` | 3.10, 3.11, 3.12 | PySide6 / Qt6 (Offscreen & Graphical) | Supported (bundled) |
| **macOS** | macOS 13+ (Ventura, Sonoma, Sequoia) | Apple Silicon (`arm64`), Intel (`x86_64`) | 3.10, 3.11, 3.12 | PySide6 / Qt6 Cocoa | Supported (bundled) |
| **Windows** | Windows 10, Windows 11 | `x86_64` | 3.10, 3.11, 3.12 | PySide6 / Qt6 DirectWrite | Supported (bundled) |

---

## Linux Installation & Operating Instructions

### Prerequisites
1. **Python 3.10, 3.11, or 3.12** and `pipx` / `pip`:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3 python3-pip python3-venv pipx
   ```
2. **Qt/PySide6 System Libraries** (required for desktop GUI on Linux):
   ```bash
   sudo apt-get install -y libegl1 libxkbcommon0 libgl1-mesa-glx
   ```

### Quick Installation

#### Option A: Source Installation (Recommended for development)
```bash
git clone https://github.com/Txdana/Peke.git
cd Peke
./install.sh --from-source
```

#### Option B: Release Wheel Installation
```bash
./install.sh
```

### Running Peke
- **Headless CLI / MCP Server:**
  ```bash
  peke --help
  peke mcp doctor
  ```
- **Desktop GUI:**
  ```bash
  peke launch
  ```
- **Offscreen GUI (CI or headless server):**
  ```bash
  QT_QPA_PLATFORM=offscreen peke launch
  ```

---

## macOS Installation & Operating Instructions

### Prerequisites
1. **Python 3.10+** (via Homebrew or Python.org installer):
   ```bash
   brew install python@3.12 pipx
   ```

### Quick Installation

#### Source Installation:
```bash
git clone https://github.com/Txdana/Peke.git
cd Peke
./install.sh --from-source
```

### Running Peke on macOS
- **Launch GUI:**
  ```bash
  peke launch
  ```
- **Run MCP Self-Test:**
  ```bash
  peke mcp doctor
  ```

---

## Local SearXNG Search Service

Peke includes a bundled, private local SearXNG runtime that binds strictly to `127.0.0.1:8888`.
No Docker daemon, administrator elevation, or external service configuration is required.

- To start or manage local search via CLI:
  ```bash
  peke search --help
  ```

---

## Local AI & GGUF Inference

- Local GGUF model support uses `llama-cpp-python`.
- **CPU Fallback:** CPU inference is always available across Linux and macOS.
- **Apple Silicon (Metal):** Acceleration is enabled automatically when compiled with Metal support.
- Model files are managed under `~/.peke/models/` and are never auto-downloaded without user action.

---

## Troubleshooting

### 1. `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` (Linux)
- **Cause:** Missing system X11/EGL libraries.
- **Fix:** Install required libraries:
  ```bash
  sudo apt-get install -y libegl1 libxkbcommon0 libgl1-mesa-glx
  ```

### 2. `pipx: command not found`
- **Cause:** `pipx` binary directory is not in user `PATH`.
- **Fix:**
  ```bash
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
  ```
  Restart your terminal session after running `ensurepath`.

### 3. MCP Handshake Issues
- **Fix:** Run the built-in MCP diagnostic tool:
  ```bash
  peke mcp doctor
  ```
