# -*- coding: utf-8 -*-
"""ui/common/state.py

Per-user UI state persistence helpers (QSettings).
- QSplitter geometry/state
- QHeaderView (table header) state

Best-effort: failures should never crash the app.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QHeaderView, QSplitter

log = logging.getLogger(__name__)

ORG_NAME = "I-SEP"
APP_NAME = "SSAA"


def _settings() -> QSettings:
    return QSettings(ORG_NAME, APP_NAME)


def save_splitter_state(splitter: QSplitter, key: str) -> None:
    try:
        _settings().setValue(key, splitter.saveState())
    except Exception:
        log.debug("save_splitter_state failed (%s)", key, exc_info=True)


def restore_splitter_state(splitter: QSplitter, key: str) -> None:
    try:
        data = _settings().value(key)
        if data is not None:
            splitter.restoreState(data)
    except Exception:
        log.debug("restore_splitter_state failed (%s)", key, exc_info=True)


def save_header_state(header: QHeaderView, key: str) -> None:
    try:
        _settings().setValue(key, header.saveState())
    except Exception:
        log.debug("save_header_state failed (%s)", key, exc_info=True)


def restore_header_state(header: QHeaderView, key: str) -> None:
    try:
        data = _settings().value(key)
        if data is not None:
            header.restoreState(data)
    except Exception:
        log.debug("restore_header_state failed (%s)", key, exc_info=True)


def get_ui_theme() -> str:
    """Return the persisted UI theme name ('light' or 'dark')."""
    try:
        val = _settings().value("ui/theme", "light")
        theme = str(val or "light").strip().lower()
        return theme if theme in ("light", "dark") else "light"
    except Exception:
        log.debug("get_ui_theme failed", exc_info=True)
        return "light"


def set_ui_theme(theme: str) -> None:
    """Persist the UI theme name."""
    try:
        theme_name = str(theme or "light").strip().lower()
        if theme_name not in ("light", "dark"):
            theme_name = "light"
        _settings().setValue("ui/theme", theme_name)
    except Exception:
        log.debug("set_ui_theme failed", exc_info=True)


def get_nav_mode() -> str:
    """Return persisted navigation mode: 'classic' or 'modern'."""
    try:
        val = _settings().value("ui/nav_mode", "classic")
        mode = str(val or "classic").strip().lower()
        return mode if mode in ("classic", "modern") else "classic"
    except Exception:
        log.debug("get_nav_mode failed", exc_info=True)
        return "classic"


def set_nav_mode(mode: str) -> None:
    """Persist navigation mode."""
    try:
        m = str(mode or "classic").strip().lower()
        _settings().setValue("ui/nav_mode", m if m in ("classic", "modern") else "classic")
    except Exception:
        log.debug("set_nav_mode failed", exc_info=True)
