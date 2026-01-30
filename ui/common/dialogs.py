# -*- coding: utf-8 -*-
"""Common dialogs helpers.

Thin wrappers around QMessageBox to keep UI consistent and reduce duplication.

These wrappers are intentionally small and dependency-free (except PyQt5).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from PyQt5.QtWidgets import QMessageBox, QWidget


def info(parent: Optional[QWidget], title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


def warn(parent: Optional[QWidget], title: str, text: str) -> None:
    QMessageBox.warning(parent, title, text)


def error(parent: Optional[QWidget], title: str, text: str, details: Optional[str] = None) -> None:
    if details:
        text = f"{text}\n\nDetalles:\n{details}"
    QMessageBox.critical(parent, title, text)


def confirm(parent: Optional[QWidget], title: str, text: str, *, default_no: bool = True) -> bool:
    """Yes/No question. Returns True if user chooses Yes."""
    default = QMessageBox.No if default_no else QMessageBox.Yes
    r = QMessageBox.question(parent, title, text, QMessageBox.Yes | QMessageBox.No, default)
    return r == QMessageBox.Yes


class SaveChoice(Enum):
    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"


def ask_save_discard_cancel(
    parent: Optional[QWidget],
    title: str,
    text: str,
    *,
    default: SaveChoice = SaveChoice.SAVE,
) -> SaveChoice:
    """Three-button question, common when leaving with unsaved changes."""
    default_btn = {
        SaveChoice.SAVE: QMessageBox.Save,
        SaveChoice.DISCARD: QMessageBox.Discard,
        SaveChoice.CANCEL: QMessageBox.Cancel,
    }[default]

    r = QMessageBox.question(
        parent,
        title,
        text,
        QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        default_btn,
    )

    if r == QMessageBox.Save:
        return SaveChoice.SAVE
    if r == QMessageBox.Discard:
        return SaveChoice.DISCARD
    return SaveChoice.CANCEL
