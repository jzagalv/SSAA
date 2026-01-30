# -*- coding: utf-8 -*-
"""ui/common/shortcuts.py

Utility helpers to install common keyboard shortcuts consistently.

Kept minimal to avoid changing behavior unexpectedly.
"""

from __future__ import annotations

from typing import Callable

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QWidget, QShortcut


def add_shortcut(parent: QWidget, sequence: QKeySequence | str, handler: Callable[[], None]) -> QShortcut:
    sc = QShortcut(QKeySequence(sequence), parent)
    sc.activated.connect(handler)
    return sc
