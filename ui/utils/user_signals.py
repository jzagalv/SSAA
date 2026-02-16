from __future__ import annotations

import logging
from typing import Callable

from PyQt5.QtWidgets import QComboBox, QLineEdit

log = logging.getLogger(__name__)


def _safe_call(handler: Callable[[str], None], value: str) -> None:
    try:
        handler(value)
    except Exception:
        log.debug("user signal handler failed (best-effort).", exc_info=True)


def connect_lineedit_user_commit(line: QLineEdit, handler: Callable[[str], None]) -> None:
    try:
        if hasattr(line, "editingFinished"):
            line.editingFinished.connect(lambda: _safe_call(handler, str(line.text())))
            return
        if hasattr(line, "returnPressed"):
            line.returnPressed.connect(lambda: _safe_call(handler, str(line.text())))
    except Exception:
        log.debug("connect_lineedit_user_commit failed (best-effort).", exc_info=True)


def connect_lineedit_user_live(line: QLineEdit, handler: Callable[[str], None]) -> None:
    try:
        if hasattr(line, "textEdited"):
            line.textEdited.connect(lambda txt: _safe_call(handler, str(txt)))
            return
        line.textChanged.connect(lambda txt: _safe_call(handler, str(txt)))
    except Exception:
        log.debug("connect_lineedit_user_live failed (best-effort).", exc_info=True)


def connect_combobox_user_changed(combo: QComboBox, handler: Callable[[str], None]) -> None:
    try:
        if hasattr(combo, "activated"):
            combo.activated.connect(lambda _i: _safe_call(handler, str(combo.currentText())))
            return
        combo.currentIndexChanged.connect(lambda _i: _safe_call(handler, str(combo.currentText())))
    except Exception:
        log.debug("connect_combobox_user_changed failed (best-effort).", exc_info=True)
