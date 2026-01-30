# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

# Allow building from an alternate source root (e.g. PyArmor-obfuscated tree).
# The packaging scripts set this env var when needed.
SRC_ROOT = os.environ.get("SSAA_SRC_ROOT", ".")

block_cipher = None
hiddenimports = collect_submodules("PyQt5") + ["jwt"]

datas = [
    (os.path.join(SRC_ROOT, "resources"), "resources"),
    (os.path.join(SRC_ROOT, "build", "build_config.json"), "."),  # build-time overrides
]

a = Analysis(
    [os.path.join(SRC_ROOT, "main.py")],
    pathex=[SRC_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SSAA",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=os.path.join(SRC_ROOT, "resources", "app.ico"),
    version=os.path.join(SRC_ROOT, "build", "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="ssaa",
)