# Installers and release integrity

## Windows desktop app (recommended)

The recommended consumer path is a source-build command. The repository contains the PowerShell installer script and the Inno Setup recipe, not a prebuilt Windows installer executable:

```powershell
irm https://raw.githubusercontent.com/Txdana/Peke/main/install.ps1 | iex
```

The script bootstraps missing build tools through `winget` when available, fetches a pinned Git commit, verifies the checked-out SHA, builds the windowed GUI with PyInstaller, compiles `Peke-Setup-<version>-x64.exe` locally with Inno Setup, runs it as a per-user installation, and launches Peke. The temporary build directory is removed afterward. The installed app creates a Start menu shortcut, offers an optional desktop shortcut, and registers an uninstaller. No model weights are bundled or downloaded; the user selects a `.gguf` file from Model Settings.

A full 40-character reviewed source SHA must be committed in `install.ps1`. The script refuses to run a real build if the pin is missing or invalid, and it never substitutes `main` or another moving branch for the pinned revision. `-DryRun` previews the actions without installing prerequisites. `-NoLaunch` builds the setup executable without installing it; `-NoBootstrap` skips automatic prerequisite installation for controlled environments.

This source-build path is distinct from publishing a prebuilt setup EXE. Do not commit generated `.exe` files or `dist/` output to the source repository.

## Linux and macOS package installer

`install.sh` is the existing verified Python package installer for Linux/macOS and automation use. It installs a published wheel into a user-level pipx environment after checking the wheel, dependency lock, and `SHA256SUMS`. It requires Python 3.10+ and pipx; it is not a native GUI installer.

```sh
curl -fsSL https://github.com/Txdana/Peke/releases/latest/download/install.sh | sh
```

For a source checkout, use `./install.sh --from-source`. For specific options and platform caveats, inspect `install.sh --dry-run` and the script help/comments.

## Developer source installation

```powershell
python -m pip install -e ".[gui,dev]"
python -m peke.desktop.launcher
```

Source mode is intended for development and may resolve dependencies from the configured package index. It is not the recommended consumer install path.

## Windows packaging

Build on Windows x64 with Python 3.12 and Inno Setup 6:

```powershell
python -m pip install -e ".[gui]" pyinstaller==6.22.3
pyinstaller packaging/windows/Peke.spec --clean --noconfirm
& "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe" packaging/windows/Peke.iss
```

The output is `dist/Peke/` plus `dist-installer/Peke-Setup-<version>-x64.exe`, with the version read from package metadata. PyInstaller cannot produce a native Windows executable when run on Linux/macOS. Test on a clean Windows VM without Python installed, including model selection, app restart, shortcuts, uninstall, and first-run experience.

Windows CI compiles the installer recipe on a Windows runner to validate packaging. This does not require committing or publishing the generated setup EXE. Build artifacts are not proof of successful GUI behavior; do a clean-machine launch test before any public release.
