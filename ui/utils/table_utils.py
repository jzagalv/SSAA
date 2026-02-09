# -*- coding: utf-8 -*-
"""Table helpers for consistent autoresize + manual resize."""
from __future__ import annotations

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QAbstractScrollArea, QHeaderView


def _get_column_count(table) -> int:
    if table is None:
        return 0
    try:
        model = table.model()
    except Exception:
        model = None
    if model is not None:
        try:
            return int(model.columnCount())
        except Exception:
            pass
    try:
        return int(table.columnCount())
    except Exception:
        return 0


def _connect_autofit_model_signals(table) -> None:
    if table is None:
        return
    try:
        model = table.model()
    except Exception:
        model = None
    if model is None:
        return

    last_model = getattr(table, "_autofit_model_ref", None)
    if last_model is model:
        return

    def _schedule(*_args):
        request_autofit(table)

    try:
        model.dataChanged.connect(_schedule)
        model.rowsInserted.connect(_schedule)
        model.columnsInserted.connect(_schedule)
        model.modelReset.connect(_schedule)
        model.layoutChanged.connect(_schedule)
    except Exception:
        pass
    setattr(table, "_autofit_model_ref", model)


def autofit_columns(table, extra_px: int = 18, max_px: int = 700) -> None:
    if table is None:
        return
    cols = _get_column_count(table)
    if cols <= 0:
        return
    try:
        header = table.horizontalHeader()
    except Exception:
        return
    header.setSectionsMovable(True)
    header.setStretchLastSection(False)
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    updates_enabled = table.updatesEnabled()
    table.setUpdatesEnabled(False)
    try:
        if hasattr(table, "resizeColumnsToContents"):
            table.resizeColumnsToContents()
        for c in range(cols):
            try:
                w = header.sectionSize(c)
            except Exception:
                try:
                    w = table.sizeHintForColumn(c)
                except Exception:
                    continue
            col_caps = getattr(table, "_autofit_column_caps", {}) or {}
            col_max = col_caps.get(c, max_px)
            w = min(int(w + extra_px), int(col_max))
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

    _connect_autofit_model_signals(table)

    timer = getattr(table, "_autofit_timer", None)
    if timer is None:
        timer = QTimer(table)
        timer.setSingleShot(True)
        timer.timeout.connect(
            lambda: autofit_columns(
                table,
                extra_px=int(getattr(table, "_autofit_extra_px", 18)),
                max_px=int(getattr(table, "_autofit_max_px", 700)),
            )
        )
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

    _connect_autofit_model_signals(table)
    request_autofit(table)
