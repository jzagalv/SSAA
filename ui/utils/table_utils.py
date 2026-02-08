# -*- coding: utf-8 -*-
"""Table helpers for consistent autoresize + manual resize."""
from __future__ import annotations

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QAbstractScrollArea, QHeaderView


def autofit_columns(table, extra_px: int = 18, max_px: int = 700) -> None:
    if table is None:
        return
    try:
        cols = table.columnCount()
    except Exception:
        cols = 0
    if cols <= 0:
        return
    header = table.horizontalHeader()
    header.setSectionsMovable(True)
    header.setStretchLastSection(False)
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    updates_enabled = table.updatesEnabled()
    table.setUpdatesEnabled(False)
    try:
        table.resizeColumnsToContents()
        for c in range(cols):
            try:
                w = header.sectionSize(c)
            except Exception:
                continue
            w = min(int(w + extra_px), int(max_px))
            try:
                header.resizeSection(c, w)
            except Exception:
                pass
        header.setSectionResizeMode(QHeaderView.Interactive)
        table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
    finally:
        table.setUpdatesEnabled(updates_enabled)


def request_autofit(table, delay_ms: int = 120) -> None:
    if table is None:
        return

    timer = getattr(table, "_autofit_timer", None)
    if timer is None:
        timer = QTimer(table)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: autofit_columns(table))
        setattr(table, "_autofit_timer", timer)

    timer.start(int(delay_ms))


def configure_table_autoresize(table) -> None:
    """Install autoresize behavior and allow manual resizing."""
    if table is None:
        return

    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setSectionsMovable(True)
    header.setSectionResizeMode(QHeaderView.Interactive)

    if not getattr(table, "_autofit_connected", False):
        try:
            model = table.model()
            if model is not None:
                def _schedule(*_args):
                    request_autofit(table)
                model.dataChanged.connect(_schedule)
                model.rowsInserted.connect(_schedule)
                model.columnsInserted.connect(_schedule)
                model.modelReset.connect(_schedule)
                model.layoutChanged.connect(_schedule)
        except Exception:
            pass
        setattr(table, "_autofit_connected", True)

    request_autofit(table)
