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
    MOMR_COL_DESC,
    MOMR_COL_PT,
    MOMR_COL_IT,
    MOMR_HEADERS,
)
from screens.cc_consumption.utils import should_persist_scenario_desc


@dataclass
class ScenarioRow:
    n: int
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
            if role != QtCore.Qt.DisplayRole:
                return None

            if col == MOMR_COL_ESC:
                return str(int(row.n))
            if col == MOMR_COL_DESC:
                return row.desc
            if col == MOMR_COL_PT:
                return f"{float(row.p_total or 0.0):.2f}"
            if col == MOMR_COL_IT:
                return f"{float(row.i_total or 0.0):.2f}"
            return None

        def setData(self, index: QtCore.QModelIndex, value, role: int = QtCore.Qt.EditRole) -> bool:
            if not index.isValid():
                return False
            if index.column() != MOMR_COL_DESC:
                return False
            if role not in (QtCore.Qt.EditRole, QtCore.Qt.DisplayRole):
                return False

            row = self._logic.row_at(index.row())
            if row is None:
                return False

            desc = str(value or "").strip()
            if not self._logic.set_desc_if_real(row.n, desc):
                return False
            row.desc = desc
            self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole])
            return True

else:

    class MomentaneosScenariosTableModel:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("PyQt5 is required to use MomentaneosScenariosTableModel")
