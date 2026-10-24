# PyInstaller spec for the windowed Peke desktop application.
# Build on Windows x64: pyinstaller packaging/windows/Peke.spec --clean --noconfirm
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

# PyInstaller resolves spec-file-relative script paths relative to the spec directory
# in some invocation contexts. Anchor every project path to the repository root.
ROOT = Path(SPECPATH).resolve().parent.parent.parent
SRC = ROOT / "src"

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

icon = SRC / "peke" / "gui" / "assets" / "peke.ico"
if not icon.is_file():
    icon = None

a = Analysis(
    [str(SRC / "peke" / "desktop" / "launcher.py")],
    pathex=[str(SRC)],
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
    icon=str(icon) if icon else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Peke")
