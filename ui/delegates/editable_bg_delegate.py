# -*- coding: utf-8 -*-
"""Delegate to paint editable cells with a consistent background."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QStyledItemDelegate

from ui.theme import get_theme_token


class EditableBgDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if index is not None:
            try:
                if (index.flags() & Qt.ItemIsEditable) and not (option.state & option.State_Selected):
                    color = QColor(get_theme_token("INPUT_EDIT_BG", "#FFF9C4"))
                    painter.save()
                    painter.fillRect(option.rect, color)
                    painter.restore()
            except Exception:
                pass
        super().paint(painter, option, index)
