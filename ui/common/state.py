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
