# -*- coding: utf-8 -*-
"""Theme/QSS application helpers.

These helpers are intentionally UI-only and free of business logic.
They support both development runs and frozen (PyInstaller) builds.
"""
from __future__ import annotations

import json
from pathlib import Path

from infra.paths import app_root


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
    qss_p = _resolve(qss_path)
    qss = qss_p.read_text(encoding="utf-8")
    theme = load_theme(theme_path)
    for k, v in theme.items():
        qss = qss.replace("{{" + k + "}}", str(v))
    app.setStyleSheet(qss)


def apply_app_theme(app) -> None:
    """Apply the default bundled QSS + theme.

    Kept for backwards compatibility with older calls that used a single argument.
    """
    return apply_qss_with_theme(app)
