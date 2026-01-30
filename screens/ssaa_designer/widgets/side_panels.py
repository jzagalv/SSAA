# -*- coding: utf-8 -*-
"""SSAA Designer - Side panels (UI only).

These helpers build the left/right panels for the designer screen:

- Issues panel (layer label, refresh button, orphan autoconnect, list)
- Feeders panel (drag&drop list + refresh button)

They intentionally only construct widgets and wire signals. Any business logic
stays in the screen/controller/pipeline.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QWidget,
)

from .feed_list_widget import FeedListWidget


def build_issues_panel(screen) -> QGroupBox:
    """Create and attach the issues panel widgets to *screen*.

    This sets attributes on the screen instance:
      - grp_issues, lbl_layer, btn_refresh_issues, btn_autoconnect_orphans, lst_issues
    """

    screen.grp_issues = QGroupBox("Validaciones / Issues")
    vis = QVBoxLayout(screen.grp_issues)

    row = QHBoxLayout()
    row.addWidget(QLabel("Capa:"))
    screen.lbl_layer = QLabel("")
    screen.lbl_layer.setObjectName("designerLayerLabel")
    row.addWidget(screen.lbl_layer, 1)

    screen.btn_refresh_issues = QPushButton("Actualizar issues")
    # Connect to a stable public API on the screen (avoid private method coupling).
    if hasattr(screen, "refresh_issues") and callable(getattr(screen, "refresh_issues")):
        screen.btn_refresh_issues.clicked.connect(screen.refresh_issues)
    else:
        screen.btn_refresh_issues.setEnabled(False)
        screen.btn_refresh_issues.setToolTip("No hay handler disponible para actualizar issues.")
    row.addWidget(screen.btn_refresh_issues)
    vis.addLayout(row)

    screen.btn_autoconnect_orphans = QPushButton("Auto-conectar huérfanos (sugerido)")
    # Connect to stable public API on the screen (avoid private method coupling).
    if hasattr(screen, "auto_connect_orphans") and callable(getattr(screen, "auto_connect_orphans")):
        screen.btn_autoconnect_orphans.clicked.connect(screen.auto_connect_orphans)
    else:
        screen.btn_autoconnect_orphans.setEnabled(False)
        screen.btn_autoconnect_orphans.setToolTip("No hay handler disponible para auto-conectar huérfanos.")
    vis.addWidget(screen.btn_autoconnect_orphans)

    screen.lst_issues = QListWidget()
    vis.addWidget(screen.lst_issues, 1)

    return screen.grp_issues


def build_feeders_panel(screen) -> QWidget:
    """Create and attach the feeders panel widgets to *screen*.

    This sets attributes on the screen instance:
      - lst_feeders, btn_refresh_feeders
    """

    right = QWidget()
    vright = QVBoxLayout(right)

    grp_feed = QGroupBox("Alimentadores disponibles (desde 'Alimentación tableros')")
    vfeed = QVBoxLayout(grp_feed)
    vfeed.addWidget(QLabel("Arrastra una carga al canvas para crear un nodo CARGA (se consume al usarla)."))

    screen.lst_feeders = FeedListWidget()
    vfeed.addWidget(screen.lst_feeders, 1)

    btn_row = QHBoxLayout()
    screen.btn_refresh_feeders = QPushButton("Actualizar")
    # Connect to stable public API on the screen (avoid private method coupling).
    if hasattr(screen, "refresh_feeders") and callable(getattr(screen, "refresh_feeders")):
        screen.btn_refresh_feeders.clicked.connect(screen.refresh_feeders)
    else:
        screen.btn_refresh_feeders.setEnabled(False)
        screen.btn_refresh_feeders.setToolTip("No hay handler disponible para actualizar alimentadores.")
    btn_row.addWidget(screen.btn_refresh_feeders)
    btn_row.addStretch(1)
    vfeed.addLayout(btn_row)

    vright.addWidget(grp_feed, 1)

    return right
