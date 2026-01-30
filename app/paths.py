# -*- coding: utf-8 -*-
"""Path helpers.

Centralized helpers to resolve resources both in dev and when packaged
(PyInstaller sets sys._MEIPASS).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def base_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def resource_path(relative: str) -> str:
    return str((base_dir() / relative).resolve())


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def user_data_dir(app_name: str = "SSAA") -> str:
    """Per-user writable directory.

    We prefer LOCALAPPDATA (no-admin installs). Fallback to APPDATA.
    """
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return ensure_dir(str(Path(root) / app_name))
