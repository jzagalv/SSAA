# -*- coding: utf-8 -*-
"""Momentaneos scenarios summary table model (MVC) and pure logic helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

try:
    from PyQt5 import QtCore
except Exception:  # pragma: no cover - optional for test environments
    QtCore = None

from screens.cc_consumption.table_schema import (
    MOMR_COL_ESC,
    MOMR_COL_PERM,
    MOMR_COL_DESC,
    MOMR_COL_PT,
    MOMR_COL_IT,
    MOMR_HEADERS,
)
from screens.cc_consumption.utils import should_persist_scenario_desc, fmt


@dataclass
class ScenarioRow:
    n: int
    include_perm: bool
    desc: str
    p_total: float
    i_total: float


class MomentaneosScenariosTableLogic:
    """Pure logic holder for Momentaneos scenario rows."""

    def __init__(self, controller: Any) -> None:
        self._controller = controller
        self._rows: List[ScenarioRow] = []

    def set_rows(self, rows: List[ScenarioRow]) -> None:
        self._rows = list(rows or [])

    def row_count(self) -> int:
        return len(self._rows)

    def row_at(self, row: int) -> Optional[ScenarioRow]:
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def set_desc_if_real(self, n: int, desc: str) -> bool:
        if not should_persist_scenario_desc(n, desc):
            return False
        setter = getattr(self._controller, "set_scenario_desc", None)
        if callable(setter):
            return bool(setter(int(n), desc, notify=False))
        return False

    def set_include_perm(self, n: int, value: bool) -> bool:
        setter = getattr(self._controller, "set_mom_scenario_include_perm", None)
        if callable(setter):
            return bool(setter(int(n), bool(value), notify=True))
        return False


if QtCore is not None:

    class MomentaneosScenariosTableModel(QtCore.QAbstractTableModel):
        """QAbstractTableModel for CC Momentaneos scenario summary."""

        def __init__(self, controller: Any, parent=None) -> None:
            super().__init__(parent)
            self._logic = MomentaneosScenariosTableLogic(controller)

        def set_rows(self, rows: List[ScenarioRow]) -> None:
            self.beginResetModel()
            self._logic.set_rows(rows)
            self.endResetModel()

        def rowCount(self, parent=QtCore.QModelIndex()) -> int:
            return 0 if parent.isValid() else self._logic.row_count()

        def columnCount(self, parent=QtCore.QModelIndex()) -> int:
            return 0 if parent.isValid() else len(MOMR_HEADERS)

        def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):
            if role != QtCore.Qt.DisplayRole:
                return None
            if orientation == QtCore.Qt.Horizontal:
                try:
                    return MOMR_HEADERS[section]
                except Exception:
                    return None
            return str(section + 1)

        def flags(self, index: QtCore.QModelIndex):
            if not index.isValid():
                return QtCore.Qt.NoItemFlags
            flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
            if index.column() == MOMR_COL_PERM:
                flags |= QtCore.Qt.ItemIsUserCheckable
            if index.column() == MOMR_COL_DESC:
                flags |= QtCore.Qt.ItemIsEditable
            return flags

        def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
            if not index.isValid():
                return None
            row = self._logic.row_at(index.row())
            if row is None:
                return None

            col = index.column()
            if col == MOMR_COL_PERM and role == QtCore.Qt.CheckStateRole:
                getter = getattr(self._logic._controller, "get_mom_scenario_include_perm", None)
                if callable(getter):
                    checked = bool(getter(row.n))
                else:
                    checked = bool(row.include_perm)
                return QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
            if role not in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
                return None

            if col == MOMR_COL_ESC:
                return int(row.n) if role == QtCore.Qt.EditRole else str(int(row.n))
            if col == MOMR_COL_PERM:
                return ""
            if col == MOMR_COL_DESC:
                return row.desc
            if col == MOMR_COL_PT:
                return float(row.p_total or 0.0) if role == QtCore.Qt.EditRole else fmt(row.p_total)
            if col == MOMR_COL_IT:
                return float(row.i_total or 0.0) if role == QtCore.Qt.EditRole else fmt(row.i_total)
            return None

        def setData(self, index: QtCore.QModelIndex, value, role: int = QtCore.Qt.EditRole) -> bool:
            if not index.isValid():
                return False
            row = self._logic.row_at(index.row())
            if row is None:
                return False

            if index.column() == MOMR_COL_PERM and role == QtCore.Qt.CheckStateRole:
                checked = value == QtCore.Qt.Checked
                if bool(row.include_perm) == bool(checked):
                    return False
                if not self._logic.set_include_perm(row.n, checked):
                    return False
                row.include_perm = bool(checked)
                self.dataChanged.emit(index, index, [QtCore.Qt.CheckStateRole, QtCore.Qt.DisplayRole])
                return True

            if index.column() != MOMR_COL_DESC:
                return False
            if role not in (QtCore.Qt.EditRole, QtCore.Qt.DisplayRole):
                return False

            desc = str(value or "").strip()
            if not self._logic.set_desc_if_real(row.n, desc):
                return False
            row.desc = desc
            self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole])
            return True

        def sort(self, column: int, order: QtCore.Qt.SortOrder = QtCore.Qt.AscendingOrder) -> None:
            reverse = order == QtCore.Qt.DescendingOrder

            def key_fn(r: ScenarioRow):
                if column == MOMR_COL_ESC:
                    return int(r.n or 0)
                if column == MOMR_COL_PERM:
                    return 1 if bool(r.include_perm) else 0
                if column == MOMR_COL_DESC:
                    return (r.desc or "").casefold()
                if column == MOMR_COL_PT:
                    return float(r.p_total or 0.0)
                if column == MOMR_COL_IT:
                    return float(r.i_total or 0.0)
                return 0

            self.layoutAboutToBeChanged.emit()
            self._logic._rows.sort(key=key_fn, reverse=reverse)
            self.layoutChanged.emit()

else:

    class MomentaneosScenariosTableModel:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("PyQt5 is required to use MomentaneosScenariosTableModel")
