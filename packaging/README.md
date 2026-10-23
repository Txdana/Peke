# Standalone PyInstaller Builds for Peke

Peke provides a PyInstaller spec file (`packaging/peke.spec`) for generating standalone binary distributions for Windows, macOS, and Linux.

## Building Standalone Executables

### Prerequisites
Install PyInstaller alongside Peke with GUI support:
```bash
pip install pyinstaller ".[gui]"
```

### Build Instructions
Run PyInstaller from the root directory of the repository:

```bash
pyinstaller packaging/peke.spec --noconfirm
```

The compiled standalone executable and bundled assets will be placed in `dist/peke/`.

> **Note:** PyInstaller builds are optional and not enabled in default CI workflows to maintain fast test pipelines.
