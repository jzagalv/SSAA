# -*- coding: utf-8 -*-
"""Theme/QSS application helpers.

These helpers are intentionally UI-only and free of business logic.
They support both development runs and frozen (PyInstaller) builds.
"""
from __future__ import annotations

import json
from pathlib import Path

from infra.paths import app_root

THEME_FILES = {
    "light": "resources/theme_light.json",
    "dark": "resources/theme_dark.json",
}

_CURRENT_THEME_NAME = "light"
_CURRENT_THEME: dict = {}


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return app_root() / p


def load_theme(theme_path: str) -> dict:
    p = _resolve(theme_path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def apply_qss_with_theme(app, qss_path: str = 'resources/styles.qss', theme_path: str = 'resources/theme.json') -> None:
    """Load a QSS file and replace {{token}} placeholders from theme JSON."""
    global _CURRENT_THEME
    qss_p = _resolve(qss_path)
    qss = qss_p.read_text(encoding="utf-8")
    theme = load_theme(theme_path)
    _CURRENT_THEME = theme or {}
    for k, v in theme.items():
        qss = qss.replace("{{" + k + "}}", str(v))
    app.setStyleSheet(qss)

def apply_named_theme(app, theme_name: str, qss_path: str = "resources/styles.qss") -> None:
    """Apply a named theme using the shared QSS template."""
    global _CURRENT_THEME_NAME
    _CURRENT_THEME_NAME = (theme_name or "light").lower().strip() or "light"
    theme_path = THEME_FILES.get(_CURRENT_THEME_NAME, THEME_FILES["light"])
    apply_qss_with_theme(app, qss_path=qss_path, theme_path=theme_path)


def get_theme_token(key: str, default: str = "") -> str:
    """Best-effort theme token lookup for UI colors."""
    global _CURRENT_THEME
    if not _CURRENT_THEME:
        theme_path = THEME_FILES.get(_CURRENT_THEME_NAME, THEME_FILES["light"])
        _CURRENT_THEME = load_theme(theme_path)
    return str(_CURRENT_THEME.get(key, default))


def apply_app_theme(app) -> None:
    """Apply the default bundled QSS + theme.

    Kept for backwards compatibility with older calls that used a single argument.
    """
    try:
        from ui.common.state import get_ui_theme
        theme_name = get_ui_theme()
    except Exception:
        theme_name = "light"
    return apply_named_theme(app, theme_name)
