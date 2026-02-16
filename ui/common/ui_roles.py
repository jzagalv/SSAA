# -*- coding: utf-8 -*-
"""Visual role tags for QSS-driven UI variants."""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget,
    QTableWidget,
    QTableView,
    QLineEdit,
    QComboBox,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QAbstractSpinBox,
)


def set_role_form(w: QWidget):
    w.setProperty("ui_role", "form")


def set_role_table(w: QWidget):
    w.setProperty("ui_role", "table")


def auto_tag_tables(root: QWidget):
    for t in root.findChildren(QTableWidget):
        set_role_table(t)
    for t in root.findChildren(QTableView):
        set_role_table(t)


def _has_ancestor(widget: QWidget, cls) -> bool:
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, cls):
            return True
        parent = parent.parentWidget()
    return False


def _is_read_only(widget: QWidget) -> bool:
    is_read_only = getattr(widget, "isReadOnly", None)
    if callable(is_read_only):
        try:
            return bool(is_read_only())
        except Exception:
            return False
    return False


def auto_tag_user_fields(root: QWidget):
    if root is None:
        return

    field_types = (
        QLineEdit,
        QComboBox,
        QTextEdit,
        QSpinBox,
        QDoubleSpinBox,
        QAbstractSpinBox,
    )

    widgets = [root]
    widgets.extend(root.findChildren(QWidget))

    for widget in widgets:
        if not isinstance(widget, field_types):
            continue
        if not widget.isEnabled():
            widget.setProperty("userField", False)
            continue
        if _is_read_only(widget):
            widget.setProperty("userField", False)
            continue
        if _has_ancestor(widget, QTableWidget):
            widget.setProperty("userField", False)
            continue
        widget.setProperty("userField", True)
