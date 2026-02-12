# -*- coding: utf-8 -*-
"""Helpers for reliable style refresh across widget trees."""
from __future__ import annotations

from PyQt5.QtWidgets import QWidget


def repolish_tree(root: QWidget) -> None:
    """Best-effort unpolish/polish/update for root and child widgets."""
    if root is None:
        return
    widgets = [root]
    widgets.extend(root.findChildren(QWidget))
    for widget in widgets:
        try:
            style = widget.style()
            if style is None:
                continue
            style.unpolish(widget)
            style.polish(widget)
            widget.update()
        except Exception:
            # Best-effort only: never break UI flow by style refresh issues.
            continue
