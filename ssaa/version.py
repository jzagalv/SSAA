# -*- coding: utf-8 -*-
"""SSAA version single source of truth."""

from __future__ import annotations

import json
from pathlib import Path

_DEFAULT_VERSION = "0.0.0"


def _read_version_json() -> str:
    try:
        root = Path(__file__).resolve().parents[1]
        version_path = root / "version.json"
        data = json.loads(version_path.read_text(encoding="utf-8"))
        return str(data.get("semver") or data.get("version") or _DEFAULT_VERSION)
    except Exception:
        return _DEFAULT_VERSION


__version__ = _read_version_json()


def get_version() -> str:
    return __version__
