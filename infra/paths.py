# -*- coding: utf-8 -*-
"""
Centralized path resolver for:
- Bundled resources (dev + PyInstaller)
- Per-user writable data (no admin required)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "SSAA"

def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")

def app_root() -> Path:
    """
    Root used to locate packaged resources.

    - PyInstaller: sys._MEIPASS points to the extraction dir.
    - Dev: project root (parent of this 'infra' folder).
    """
    if _is_frozen():
        return Path(getattr(sys, "_MEIPASS"))  # type: ignore[arg-type]
    return Path(__file__).resolve().parents[1]

def resources_dir() -> Path:
    """
    Location of packaged resources.
    Prefers '<root>/resources' if it exists, otherwise falls back to root.
    """
    root = app_root()
    cand = root / "resources"
    return cand if cand.exists() else root

def resource_path(rel: str) -> Path:
    return resources_dir() / rel

def user_data_dir() -> Path:
    """
    Per-user writable directory (no admin). Prefer LOCALAPPDATA (non-roaming).
    """
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def logs_dir() -> Path:
    return ensure_dir(user_data_dir() / "logs")

def libs_dir() -> Path:
    return ensure_dir(user_data_dir() / "libs")
