# -*- coding: utf-8 -*-
"""Table helpers for consistent autoresize + manual resize."""
from __future__ import annotations

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QAbstractScrollArea, QHeaderView


def _get_model(table):
    if table is None:
        return None
    try:
        return table.model()
    except Exception:
        return None


def _get_column_count(table) -> int:
    if table is None:
        return 0
    model = _get_model(table)
    if model is not None:
        try:
            return int(model.columnCount())
        except Exception:
            pass
    try:
        return int(table.columnCount())
    except Exception:
        return 0


def _get_row_count(table) -> int:
    if table is None:
        return 0
    model = _get_model(table)
    if model is not None:
        try:
            return int(model.rowCount())
        except Exception:
            pass
    try:
        return int(table.rowCount())
    except Exception:
        return 0


def _is_column_hidden(table, column: int) -> bool:
    try:
        return bool(table.isColumnHidden(int(column)))
    except Exception:
        return False


def _model_header_text(table, column: int) -> str:
    model = _get_model(table)
    if model is None:
        return ""
    try:
        val = model.headerData(int(column), Qt.Horizontal, Qt.DisplayRole)
    except Exception:
        val = ""
    return "" if val is None else str(val)


def _model_cell_text(table, row: int, column: int) -> str:
    model = _get_model(table)
    if model is None:
        return ""
    try:
        idx = model.index(int(row), int(column))
        if not idx.isValid():
            return ""
        val = model.data(idx, Qt.DisplayRole)
    except Exception:
        val = ""
    return "" if val is None else str(val)


def _iter_sample_rows(total_rows: int, max_samples: int):
    if total_rows <= 0:
        return
    if max_samples <= 0 or total_rows <= max_samples:
        for r in range(total_rows):
            yield r
        return
    step = max(1, total_rows // max_samples)
    seen = 0
    r = 0
    while r < total_rows and seen < max_samples:
        yield r
        r += step
        seen += 1
    if (total_rows - 1) not in {0, r - step}:
        yield total_rows - 1


def _connect_autofit_model_signals(table) -> None:
    if table is None:
        return
    model = _get_model(table)
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
    """Auto-fit using model/header text (QTableView/QTableWidget) + safety caps."""
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
    header.setSectionResizeMode(QHeaderView.Interactive)
    updates_enabled = table.updatesEnabled()
    table.setUpdatesEnabled(False)
    try:
        # Baseline from delegate/style hints.
        if hasattr(table, "resizeColumnsToContents"):
            table.resizeColumnsToContents()
        rows = _get_row_count(table)
        sample_rows = int(getattr(table, "_autofit_sample_rows", 200) or 200)
        min_px_default = int(getattr(table, "_autofit_min_px", 56) or 56)
        col_caps = getattr(table, "_autofit_column_caps", {}) or {}
        col_mins = getattr(table, "_autofit_column_mins", {}) or {}
        fm = table.fontMetrics()
        hfm = header.fontMetrics() if hasattr(header, "fontMetrics") else fm
        for c in range(cols):
            if _is_column_hidden(table, c):
                continue
            try:
                w = header.sectionSize(c)
            except Exception:
                try:
                    w = table.sizeHintForColumn(c)
                except Exception:
                    w = 0
            # Measure longest textual content from model sample + header.
            text_w = int(hfm.horizontalAdvance(_model_header_text(table, c) or "")) + 12
            if rows > 0:
                for r in _iter_sample_rows(rows, sample_rows):
                    cell_text = _model_cell_text(table, r, c)
                    if not cell_text:
                        continue
                    tw = int(fm.horizontalAdvance(cell_text))
                    if tw > text_w:
                        text_w = tw
            min_px = int(col_mins.get(c, min_px_default))
            col_max = col_caps.get(c, max_px)
            w = max(int(w), int(text_w))
            w = int(w + extra_px)
            w = max(int(min_px), min(int(w), int(col_max)))
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
