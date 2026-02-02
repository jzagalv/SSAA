# -*- coding: utf-8 -*-
"""Momentaneos loads table model (MVC) and pure logic helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

try:
    from PyQt5 import QtCore, QtWidgets
except Exception:  # pragma: no cover - optional for test environments
    QtCore = None
    QtWidgets = None

from screens.cc_consumption.table_schema import (
    MOM_COL_GAB,
    MOM_COL_TAG,
    MOM_COL_DESC,
    MOM_COL_PEFF,
    MOM_COL_I,
    MOM_COL_INCLUIR,
    MOM_COL_ESC,
    MOM_HEADERS,
)


@dataclass
class MomentaneoLoadRow:
    comp_id: str
    gab_label: str
    tag: str
    desc: str
    p_eff: float
    i_eff: float
    incluir: bool
    escenario: int


class MomentaneosLoadsTableLogic:
    """Pure logic holder for Momentaneos loads rows."""

    def __init__(self) -> None:
        self._rows: List[MomentaneoLoadRow] = []

    def set_items(self, items: List[Any]) -> None:
        rows: List[MomentaneoLoadRow] = []
        for it in items or []:
            rows.append(
                MomentaneoLoadRow(
                    comp_id=str(getattr(it, "comp_id", "") or ""),
                    gab_label=f"{getattr(it, 'gab_tag', '')} - {getattr(it, 'gab_nombre', '')}".strip(" -"),
                    tag=str(getattr(it, "tag_comp", "") or ""),
                    desc=str(getattr(it, "desc", "") or ""),
                    p_eff=float(getattr(it, "p_eff", 0.0) or 0.0),
                    i_eff=float(getattr(it, "i_eff", 0.0) or 0.0),
                    incluir=bool(getattr(it, "mom_incluir", True)),
                    escenario=int(getattr(it, "mom_escenario", 1) or 1),
                )
            )
        self._rows = rows

    def row_count(self) -> int:
        return len(self._rows)

    def row_at(self, row: int) -> Optional[MomentaneoLoadRow]:
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def set_incluir(self, row: int, incluir: bool) -> bool:
        r = self.row_at(row)
        if r is None:
            return False
        if r.incluir == bool(incluir):
            return False
        r.incluir = bool(incluir)
        return True

    def set_escenario(self, row: int, esc: int) -> bool:
        r = self.row_at(row)
        if r is None:
            return False
        esc = int(esc or 1)
        if esc < 1:
            esc = 1
        if r.escenario == esc:
            return False
        r.escenario = esc
        return True


if QtCore is not None and QtWidgets is not None:

    class ScenarioComboDelegate(QtWidgets.QStyledItemDelegate):
        def __init__(self, parent=None, *, min_value: int = 1, max_value: int = 20):
            super().__init__(parent)
            self._min = int(min_value)
            self._max = int(max_value)

        def set_range(self, min_value: int, max_value: int) -> None:
            self._min = int(min_value)
            self._max = int(max_value)

        def createEditor(self, parent, option, index):
            cb = QtWidgets.QComboBox(parent)
            for n in range(self._min, self._max + 1):
                cb.addItem(str(n), n)
            return cb

        def setEditorData(self, editor, index):
            try:
                current = int(index.data(QtCore.Qt.DisplayRole) or 1)
            except Exception:
                current = 1
            idx = editor.findData(current)
            editor.setCurrentIndex(0 if idx < 0 else idx)

        def setModelData(self, editor, model, index):
            value = editor.currentData()
            model.setData(index, value, QtCore.Qt.EditRole)

    class MomentaneosLoadsTableModel(QtCore.QAbstractTableModel):
        """QAbstractTableModel for CC Momentaneos loads."""

        def __init__(self, controller: Any, parent=None) -> None:
            super().__init__(parent)
            self._logic = MomentaneosLoadsTableLogic()
            self._controller = controller

        def set_items(self, items: List[Any]) -> None:
            self.beginResetModel()
            self._logic.set_items(items)
            self.endResetModel()

        def rowCount(self, parent=QtCore.QModelIndex()) -> int:
            return 0 if parent.isValid() else self._logic.row_count()

        def columnCount(self, parent=QtCore.QModelIndex()) -> int:
            return 0 if parent.isValid() else len(MOM_HEADERS)

        def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):
            if role != QtCore.Qt.DisplayRole:
                return None
            if orientation == QtCore.Qt.Horizontal:
                try:
                    return MOM_HEADERS[section]
                except Exception:
                    return None
            return str(section + 1)

        def flags(self, index: QtCore.QModelIndex):
            if not index.isValid():
                return QtCore.Qt.NoItemFlags
            flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
            if index.column() == MOM_COL_INCLUIR:
                flags |= QtCore.Qt.ItemIsUserCheckable
            if index.column() == MOM_COL_ESC:
                flags |= QtCore.Qt.ItemIsEditable
            return flags

        def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
            if not index.isValid():
                return None
            row = self._logic.row_at(index.row())
            if row is None:
                return None

            col = index.column()
            if col == MOM_COL_INCLUIR:
                if role == QtCore.Qt.CheckStateRole:
                    return QtCore.Qt.Checked if row.incluir else QtCore.Qt.Unchecked
                if role == QtCore.Qt.DisplayRole:
                    return ""
                return None

            if role != QtCore.Qt.DisplayRole:
                return None

            if col == MOM_COL_GAB:
                return row.gab_label
            if col == MOM_COL_TAG:
                return row.tag
            if col == MOM_COL_DESC:
                return row.desc
            if col == MOM_COL_PEFF:
                return "" if row.p_eff == 0 else f"{row.p_eff:.2f}"
            if col == MOM_COL_I:
                return "" if row.i_eff == 0 else f"{row.i_eff:.2f}"
            if col == MOM_COL_ESC:
                return str(row.escenario)
            return None

        def setData(self, index: QtCore.QModelIndex, value, role: int = QtCore.Qt.EditRole) -> bool:
            if not index.isValid():
                return False
            row = self._logic.row_at(index.row())
            if row is None or not row.comp_id:
                return False

            if index.column() == MOM_COL_INCLUIR and role == QtCore.Qt.CheckStateRole:
                incluir = (value == QtCore.Qt.Checked)
                changed = self._logic.set_incluir(index.row(), incluir)
                if changed:
                    self._controller.set_momentary_flags(row.comp_id, incluir, row.escenario)
                    self.dataChanged.emit(index, index, [QtCore.Qt.CheckStateRole])
                return changed

            if index.column() == MOM_COL_ESC and role in (QtCore.Qt.EditRole, QtCore.Qt.DisplayRole):
                try:
                    esc = int(value)
                except Exception:
                    esc = 1
                changed = self._logic.set_escenario(index.row(), esc)
                if changed:
                    self._controller.set_momentary_flags(row.comp_id, row.incluir, esc)
                    self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole])
                return changed

            return False

        def get_row(self, row: int) -> Optional[MomentaneoLoadRow]:
            return self._logic.row_at(row)

        def set_row_escenario(self, row: int, esc: int) -> bool:
            changed = self._logic.set_escenario(row, esc)
            if changed:
                self.dataChanged.emit(self.index(row, MOM_COL_ESC), self.index(row, MOM_COL_ESC), [QtCore.Qt.DisplayRole])
            return changed

else:

    class MomentaneosLoadsTableModel:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("PyQt5 is required to use MomentaneosLoadsTableModel")
