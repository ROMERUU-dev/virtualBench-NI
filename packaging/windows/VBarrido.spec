# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


hiddenimports = collect_submodules("pyvirtualbench")
project_root = Path(SPECPATH).resolve().parents[1]


a = Analysis(
    [str(project_root / "packaging" / "windows" / "entrypoint.py")],
    pathex=[str(project_root / "src"), str(project_root)],
    binaries=[],
    datas=[(str(project_root / "info.png"), ".")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="VBarrido",
    icon=str(project_root / "assets" / "branding" / "vbarrido.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
