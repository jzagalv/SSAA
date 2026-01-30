# -*- coding: utf-8 -*-
"""
Generate build-time version artifacts from version.json:
- build/version_info.txt (PyInstaller Windows version resource)
- build/inno/version.iss (Inno Setup #define MyAppVersion)

Run:
    python build/generate_version_artifacts.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_JSON = ROOT / "version.json"

def _numeric(ver: str) -> tuple[int,int,int,int]:
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", ver)
    if not m:
        return (1,0,0,0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), 0)

def write_pyinstaller_version(ver: str) -> None:
    a,b,c,d = _numeric(ver)
    out = ROOT / "build" / "version_info.txt"
    out.write_text(f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({a}, {b}, {c}, {d}),
    prodvers=({a}, {b}, {c}, {d}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'I-SEP'),
        StringStruct('FileDescription', 'SSAA - Diseño de Servicios Auxiliares'),
        StringStruct('FileVersion', '{ver}'),
        StringStruct('InternalName', 'SSAA'),
        StringStruct('LegalCopyright', '© I-SEP'),
        StringStruct('OriginalFilename', 'SSAA.exe'),
        StringStruct('ProductName', 'SSAA'),
        StringStruct('ProductVersion', '{ver}')])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding="utf-8")

def write_inno_version(ver: str) -> None:
    a,b,c,d = _numeric(ver)
    out = ROOT / "build" / "inno" / "version.iss"
    out.write_text(
        f'#define MyAppVersion "{ver}"\n#define MyAppVersionNumeric "{a}.{b}.{c}.{d}"\n',
        encoding="utf-8"
    )

def main() -> None:
    data = json.loads(VERSION_JSON.read_text(encoding="utf-8"))
    ver = data.get("version", "1.0.0")
    write_pyinstaller_version(ver)
    write_inno_version(ver)

if __name__ == "__main__":
    main()
