# PyInstaller spec for the windowed Peke desktop application.
# Build on Windows x64: pyinstaller packaging/windows/Peke.spec --clean --noconfirm
from PyInstaller.utils.hooks import collect_all, collect_submodules

hiddenimports = []
datas = []
binaries = []
for package in ("peke", "searx", "scrapling", "curl_cffi", "babel", "flask_babel"):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        # Optional upstream integrations may not be importable in every packaging profile.
        pass
hiddenimports += collect_submodules("peke")

icon = "src/peke/gui/assets/peke.ico"
import os
if not os.path.isfile(icon):
    icon = None

a = Analysis(
    ["src/peke/desktop/launcher.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff", "mypy", "bandit", "pip_audit"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Peke",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=icon,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Peke")
