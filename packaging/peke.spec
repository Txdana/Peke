# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = [
    ('../src/peke/gui/assets', 'peke/gui/assets'),
    ('../src/peke/gui/theme.qss', 'peke/gui'),
]
datas += collect_data_files('peke')

hiddenimports = [
    'peke',
    'peke.cli',
    'peke.gui.app',
    'peke.gui.splash',
    'peke.banner',
]
hiddenimports += collect_submodules('PySide6')
hiddenimports += collect_submodules('scrapling')

a = Analysis(
    ['../src/peke/cli.py'],
    pathex=['../src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='peke',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../src/peke/gui/assets/icon.svg',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='peke',
)
