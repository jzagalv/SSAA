# -*- coding: utf-8 -*-
"""
User settings stored in a per-user writable folder (no admin).
This replaces any "portable settings beside the executable", which breaks under installers / PyInstaller.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from infra.paths import user_data_dir, resource_path, resources_dir, libs_dir

SETTINGS_FILE: Path = user_data_dir() / "ssaa_settings.json"
log = logging.getLogger(__name__)

def _find_resource_lib(preferred: str, pattern: str) -> Path | None:
    base = resource_path(preferred)
    if base.exists():
        return base
    candidates = sorted(resources_dir().glob(pattern))
    return candidates[0] if candidates else None

def _empty_consumos_lib() -> Dict[str, Any]:
    return {
        "file_type": "SSAA_LIB_CONSUMOS",
        "name": "Consumos",
        "version": "1.0",
        "items": [],
        "schema_version": 1,
    }

def _empty_materiales_lib() -> Dict[str, Any]:
    return {
        "file_type": "SSAA_LIB_MATERIALES",
        "schema_version": 1,
        "name": "Materiales",
        "items": {
            "batteries": [],
            "battery_banks": [],
            "mcb": [],
            "mccb": [],
            "rccb": [],
            "rccb_mcb": [],
        },
    }

def _defaults() -> Dict[str, Any]:
    # Base packaged libs (inside resources/)
    base_consumos = _find_resource_lib("consumos.lib", "consumos*.lib") or resource_path("consumos.lib")
    # Prefer stable materiales.lib, fallback to any materiales*.lib
    base_materiales = _find_resource_lib("materiales.lib", "materiales*.lib") or resource_path("materiales.lib")

    # Copy-to-user defaults (paths will be set by ensure_seed_libs)
    return {
        "consumos_lib_path": str(base_consumos),
        "materiales_lib_path": str(base_materiales),
    }

def load_settings() -> Dict[str, Any]:
    defaults = _defaults()
    if not SETTINGS_FILE.exists():
        save_settings(defaults.copy())
        return defaults.copy()

    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        merged = defaults.copy()
        if isinstance(data, dict):
            merged.update({k: v for k, v in data.items() if v is not None})
        return merged
    except Exception:
        # Recover from corruption gracefully
        save_settings(defaults.copy())
        return defaults.copy()

def save_settings(data: Dict[str, Any]) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def ensure_seed_libs() -> Dict[str, Any]:
    """
    Ensures the app works out-of-the-box:
    - Copies packaged base *.lib to the per-user libs folder (if missing)
    - Writes settings defaults to point to these per-user copies (if settings missing or invalid)
    """
    s = load_settings()

    user_libs = libs_dir()

    base_consumos = _find_resource_lib("consumos.lib", "consumos*.lib")
    base_materiales = _find_resource_lib("materiales.lib", "materiales*.lib")

    user_consumos = user_libs / "consumos.lib"
    user_materiales = user_libs / "materiales.lib"

    import shutil

    if base_consumos is not None and base_consumos.exists() and not user_consumos.exists():
        shutil.copy2(base_consumos, user_consumos)
    elif not user_consumos.exists():
        log.warning("consumos.lib not found; creating empty library at %s", user_consumos)
        user_consumos.write_text(json.dumps(_empty_consumos_lib(), ensure_ascii=False, indent=2), encoding="utf-8")

    if base_materiales is not None and base_materiales.exists() and not user_materiales.exists():
        # Normalize the target name to a stable "materiales.lib"
        shutil.copy2(base_materiales, user_materiales)
    elif not user_materiales.exists():
        log.warning("materiales.lib not found; creating empty library at %s", user_materiales)
        user_materiales.write_text(json.dumps(_empty_materiales_lib(), ensure_ascii=False, indent=2), encoding="utf-8")

    # Point settings to user copies if empty or broken
    from pathlib import Path as _P
    cons_p = _P(str(s.get("consumos_lib_path", "") or "")).expanduser()
    mat_p = _P(str(s.get("materiales_lib_path", "") or "")).expanduser()

    if not cons_p.exists():
        if user_consumos.exists():
            s["consumos_lib_path"] = str(user_consumos)
        elif base_consumos is not None and base_consumos.exists():
            s["consumos_lib_path"] = str(base_consumos)

    if not mat_p.exists():
        if user_materiales.exists():
            s["materiales_lib_path"] = str(user_materiales)
        elif base_materiales is not None and base_materiales.exists():
            s["materiales_lib_path"] = str(base_materiales)

    save_settings(s)
    return s



def repair_user_space() -> None:
    """Repair per-user writable data.

    This is safe to run without admin rights and is intended for installer shortcuts like
    'Repair installation'. It:
    - Resets settings to defaults
    - Re-seeds packaged base libraries into the per-user libs folder
    """
    try:
        if SETTINGS_FILE.exists():
            SETTINGS_FILE.unlink()
    except Exception:
        pass
    # Best-effort: remove user libs to force reseed
    try:
        ulibs = libs_dir()
        if ulibs.exists():
            for p in ulibs.glob("*.lib"):
                try:
                    p.unlink()
                except Exception:
                    pass
    except Exception:
        pass
    # Recreate defaults and libs
    ensure_seed_libs()
