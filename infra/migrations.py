# -*- coding: utf-8 -*-
"""Lightweight migration framework for per-user data.

Why this exists:
- Installers overwrite the app folder on upgrade
- Per-user data lives in %APPDATA%/SSAA (settings, libs, license cache/state)
- When we change schemas/keys, we must migrate deterministically.

Design principles:
- Best-effort, never brick startup
- Idempotent migrations
- Single state file to track last applied app version + schema version
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional

from infra.paths import user_data_dir
from app.version import __version__

STATE_FILE: Path = user_data_dir() / "app_state.json"

@dataclass
class AppState:
    last_version: str = ""
    settings_schema: int = 1

def _load_state() -> AppState:
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return AppState(
                last_version=str(data.get("last_version","") or ""),
                settings_schema=int(data.get("settings_schema", 1) or 1),
            )
    except Exception:
        pass
    return AppState()

def _save_state(st: AppState) -> None:
    try:
        STATE_FILE.write_text(
            json.dumps({"last_version": st.last_version, "settings_schema": st.settings_schema}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        # Never block startup
        pass

def _migrate_settings_schema_v1_to_v2() -> None:
    """Example migration: ensure new keys exist in ssaa_settings.json."""
    try:
        from infra.settings import load_settings, save_settings, _defaults  # type: ignore
        s = load_settings()
        d = _defaults()
        changed = False
        for k, v in d.items():
            if k not in s:
                s[k] = v
                changed = True
        if changed:
            save_settings(s)
    except Exception:
        pass

def migrate_if_needed(current_version: Optional[str] = None) -> None:
    """Run migrations once per app version.

    - Uses %APPDATA%/SSAA/app_state.json to track last applied version.
    - If state missing/corrupted: does nothing dangerous.
    """
    cv = current_version or __version__
    st = _load_state()

    if st.last_version == cv:
        return

    # Schema migrations (settings)
    # We keep these decoupled from semver; bump schema int when needed.
    target_schema = 2
    if st.settings_schema < 2:
        _migrate_settings_schema_v1_to_v2()
        st.settings_schema = 2

    st.last_version = cv
    _save_state(st)
