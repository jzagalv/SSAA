# -*- coding: utf-8 -*-
"""Aleatorios table model (MVC) and pure logic helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

try:
    from PyQt5 import QtCore
except Exception:  # pragma: no cover - optional for test environments
    QtCore = None

from screens.cc_consumption.table_schema import (
    ALE_COL_SEL,
    ALE_COL_GAB,
    ALE_COL_TAG,
    ALE_COL_DESC,
    ALE_COL_PEFF,
    ALE_COL_I,
    ALE_HEADERS,
)
from screens.cc_consumption.utils import fmt


@dataclass
class AleatorioRow:
    comp_id: str
    gab_label: str
    tag: str
    desc: str
    p_eff: float
    i_eff: float


class AleatoriosTableLogic:
    """Pure logic holder for Aleatorios rows."""

    def __init__(self, controller: Any) -> None:
        self._controller = controller
        self._rows: List[AleatorioRow] = []

    def set_items(self, items: List[Any]) -> None:
        rows: List[AleatorioRow] = []
        for it in items or []:
            rows.append(
                AleatorioRow(
                    comp_id=str(getattr(it, "comp_id", "") or ""),
                    gab_label=f"{getattr(it, 'gab_tag', '')} - {getattr(it, 'gab_nombre', '')}".strip(" -"),
                    tag=str(getattr(it, "tag_comp", "") or ""),
                    desc=str(getattr(it, "desc", "") or ""),
                    p_eff=float(getattr(it, "p_eff", 0.0) or 0.0),
                    i_eff=float(getattr(it, "i_eff", 0.0) or 0.0),
                )
            )
        self._rows = rows

    def row_count(self) -> int:
        return len(self._rows)

    def row_at(self, row: int) -> Optional[AleatorioRow]:
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def get_selected(self, comp_id: str) -> bool:
        if not comp_id:
            return False
        getter = getattr(self._controller, "get_random_selected", None)
        if callable(getter):
            return bool(getter(comp_id))
        return False

    def set_selected(self, comp_id: str, selected: bool) -> bool:
        if not comp_id:
            return False
        setter = getattr(self._controller, "set_random_selected", None)
        if callable(setter):
            return bool(setter(comp_id, selected))
        return False


if QtCore is not None:

    class AleatoriosTableModel(QtCore.QAbstractTableModel):
        """QAbstractTableModel for CC Aleatorios."""

        def __init__(self, controller: Any, parent=None) -> None:
            super().__init__(parent)
            self._logic = AleatoriosTableLogic(controller)

        def set_items(self, items: List[Any]) -> None:
            self.beginResetModel()
            self._logic.set_items(items)
            self.endResetModel()

        def rowCount(self, parent=QtCore.QModelIndex()) -> int:
            return 0 if parent.isValid() else self._logic.row_count()

        def columnCount(self, parent=QtCore.QModelIndex()) -> int:
            return 0 if parent.isValid() else len(ALE_HEADERS)

        def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):
            if role != QtCore.Qt.DisplayRole:
                return None
            if orientation == QtCore.Qt.Horizontal:
                try:
                    return ALE_HEADERS[section]
                except Exception:
                    return None
            return str(section + 1)

        def flags(self, index: QtCore.QModelIndex):
            if not index.isValid():
                return QtCore.Qt.NoItemFlags
            flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
            if index.column() == ALE_COL_SEL:
                flags |= QtCore.Qt.ItemIsUserCheckable
            return flags

        def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
            if not index.isValid():
                return None
            row = self._logic.row_at(index.row())
            if row is None:
                return None

            col = index.column()
            if col == ALE_COL_SEL:
                if role == QtCore.Qt.CheckStateRole:
                    return QtCore.Qt.Checked if self._logic.get_selected(row.comp_id) else QtCore.Qt.Unchecked
                if role == QtCore.Qt.DisplayRole:
                    return ""
                return None

            if role not in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
                return None

            if col == ALE_COL_GAB:
                return row.gab_label
            if col == ALE_COL_TAG:
                return row.tag
            if col == ALE_COL_DESC:
                return row.desc
            if col == ALE_COL_PEFF:
                return float(row.p_eff) if role == QtCore.Qt.EditRole else fmt(row.p_eff)
            if col == ALE_COL_I:
                return float(row.i_eff) if role == QtCore.Qt.EditRole else fmt(row.i_eff)
            return None

        def setData(self, index: QtCore.QModelIndex, value, role: int = QtCore.Qt.EditRole) -> bool:
            if not index.isValid():
                return False
            if index.column() != ALE_COL_SEL:
                return False
            if role != QtCore.Qt.CheckStateRole:
                return False
            row = self._logic.row_at(index.row())
            if row is None:
                return False
            selected = (value == QtCore.Qt.Checked)
            changed = self._logic.set_selected(row.comp_id, selected)
            if changed:
                self.dataChanged.emit(index, index, [QtCore.Qt.CheckStateRole])
            return changed

        def sort(self, column: int, order: QtCore.Qt.SortOrder = QtCore.Qt.AscendingOrder) -> None:
            reverse = order == QtCore.Qt.DescendingOrder

            def key_fn(r: AleatorioRow):
                if column == ALE_COL_SEL:
                    return 1 if self._logic.get_selected(r.comp_id) else 0
                if column == ALE_COL_GAB:
                    return (r.gab_label or "").casefold()
                if column == ALE_COL_TAG:
                    return (r.tag or "").casefold()
                if column == ALE_COL_DESC:
                    return (r.desc or "").casefold()
                if column == ALE_COL_PEFF:
                    return float(r.p_eff or 0.0)
                if column == ALE_COL_I:
                    return float(r.i_eff or 0.0)
                return 0

            self.layoutAboutToBeChanged.emit()
            self._logic._rows.sort(key=key_fn, reverse=reverse)
            self.layoutChanged.emit()

else:

    class AleatoriosTableModel:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("PyQt5 is required to use AleatoriosTableModel")
