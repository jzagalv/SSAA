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
from .source_list_widget import SourceListWidget
from .board_list_widget import BoardListWidget


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

    screen.btn_order_diagram = QPushButton("Ordenar diagrama")
    if hasattr(screen, "order_diagram") and callable(getattr(screen, "order_diagram")):
        screen.btn_order_diagram.clicked.connect(screen.order_diagram)
    else:
        screen.btn_order_diagram.setEnabled(False)
        screen.btn_order_diagram.setToolTip("No hay handler disponible para ordenar el diagrama.")
    row.addWidget(screen.btn_order_diagram)
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

    grp_feed = QGroupBox("Cargas disponibles (desde 'Alimentación tableros')")
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
        screen.btn_refresh_feeders.setToolTip("No hay handler disponible para actualizar cargas.")
    btn_row.addWidget(screen.btn_refresh_feeders)
    btn_row.addStretch(1)
    vfeed.addLayout(btn_row)

    vright.addWidget(grp_feed, 1)

    return right


def build_sources_panel(screen) -> QWidget:
    """Create and attach the sources panel widgets to *screen*.

    This sets attributes on the screen instance:
      - lst_sources, btn_refresh_sources
    """
    right = QWidget()
    vright = QVBoxLayout(right)

    grp_src = QGroupBox("Fuentes disponibles (desde 'Instalaciones')")
    vsrc = QVBoxLayout(grp_src)
    vsrc.addWidget(QLabel("Arrastra una fuente al canvas para crear un nodo FUENTE (no se consume)."))

    screen.lst_sources = SourceListWidget()
    vsrc.addWidget(screen.lst_sources, 1)

    btn_row = QHBoxLayout()
    screen.btn_refresh_sources = QPushButton("Actualizar")
    if hasattr(screen, "refresh_sources") and callable(getattr(screen, "refresh_sources")):
        screen.btn_refresh_sources.clicked.connect(screen.refresh_sources)
    else:
        screen.btn_refresh_sources.setEnabled(False)
        screen.btn_refresh_sources.setToolTip("No hay handler disponible para actualizar fuentes.")
    btn_row.addWidget(screen.btn_refresh_sources)
    btn_row.addStretch(1)
    vsrc.addLayout(btn_row)

    vright.addWidget(grp_src, 1)

    return right


def build_boards_panel(screen) -> QWidget:
    """Create and attach the boards panel widgets to *screen*.

    This sets attributes on the screen instance:
      - lst_boards, btn_refresh_boards
    """
    right = QWidget()
    vright = QVBoxLayout(right)

    grp_boards = QGroupBox("Tableros/Fuentes disponibles (desde 'Instalaciones' - TD/TG)")
    vlist = QVBoxLayout(grp_boards)
    vlist.addWidget(QLabel("Arrastra un tablero para crear un nodo raíz (no consumible)."))

    screen.lst_boards = BoardListWidget()
    vlist.addWidget(screen.lst_boards, 1)

    btn_row = QHBoxLayout()
    screen.btn_refresh_boards = QPushButton("Actualizar")
    if hasattr(screen, "refresh_boards") and callable(getattr(screen, "refresh_boards")):
        screen.btn_refresh_boards.clicked.connect(screen.refresh_boards)
    else:
        screen.btn_refresh_boards.setEnabled(False)
        screen.btn_refresh_boards.setToolTip("No hay handler disponible para actualizar tableros.")
    btn_row.addWidget(screen.btn_refresh_boards)
    btn_row.addStretch(1)
    vlist.addLayout(btn_row)

    vright.addWidget(grp_boards, 1)

    return right
