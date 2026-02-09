# -*- coding: utf-8 -*-
"""Visual role tags for QSS-driven UI variants."""
from __future__ import annotations

from PyQt5.QtWidgets import QWidget, QTableWidget


def set_role_form(w: QWidget):
    w.setProperty("ui_role", "form")


def set_role_table(w: QWidget):
    w.setProperty("ui_role", "table")


def auto_tag_tables(root: QWidget):
    for t in root.findChildren(QTableWidget):
        set_role_table(t)
