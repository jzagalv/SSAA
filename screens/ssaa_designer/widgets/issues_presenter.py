# -*- coding: utf-8 -*-
"""IssuesPresenter

UI-only rendering for SSAA Designer issues list.

This module intentionally contains *only* Qt/UI logic (colors, icons, list items).
All rule evaluation and issue generation must live in controller/screen logic.
"""

from __future__ import annotations

from typing import Dict, List

from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import QListWidgetItem
from ui.theme import get_theme_token


def _theme_color(token: str, fallback: str) -> QColor:
    return QColor(get_theme_token(token, fallback))


class IssuesPresenter:
    """Renders issues into the screen's QListWidget (lst_issues)."""

    def __init__(self, screen):
        self.screen = screen

    def render(self, issues: List[Dict], layer: Dict) -> None:
        scr = self.screen
        if not hasattr(scr, "lst_issues"):
            return

        scr.lst_issues.clear()

        for it in issues:
            lvl = it.get("level")
            prefix = "🔴" if lvl == "error" else ("🟡" if lvl == "warn" else "ℹ️")
            item = QListWidgetItem(f"{prefix} [{it.get('code')}] {it.get('msg')}")

            # Colores por severidad (sobrio estilo CAD)
            if lvl == "error":
                item.setForeground(_theme_color("ERROR_TEXT", "#B40000"))
                item.setBackground(QBrush(_theme_color("ERROR_BG", "#FFEBEB")))
            elif lvl == "warn":
                item.setForeground(_theme_color("WARN_TEXT", "#8C5A00"))
                item.setBackground(QBrush(_theme_color("WARN_BG", "#FFF9E6")))
            else:
                item.setForeground(_theme_color("INFO_TEXT", "#1E468C"))
                item.setBackground(QBrush(_theme_color("INFO_BG", "#EBF3FF")))

            scr.lst_issues.addItem(item)

        # Enable/disable orphan helper
        has_orphans = any(i.get("code") == "NODE_ORPHAN" for i in issues)
        if hasattr(scr, "btn_autoconnect_orphans"):
            scr.btn_autoconnect_orphans.setEnabled(bool(has_orphans))

        # Cache last results for contextual actions
        scr._last_layer_issues = issues
        scr._last_issue_layer = layer
