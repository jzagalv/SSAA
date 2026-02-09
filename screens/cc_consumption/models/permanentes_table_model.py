# -*- coding: utf-8 -*-
"""Permanentes table model (MVC) and pure logic helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

try:
    from PyQt5 import QtCore
except Exception:  # pragma: no cover - optional for test environments
    QtCore = None

from screens.cc_consumption.table_schema import (
    PERM_COL_GAB,
    PERM_COL_TAG,
    PERM_COL_DESC,
    PERM_COL_PW,
    PERM_COL_PCT,
    PERM_COL_P_PERM,
    PERM_COL_I,
    PERM_COL_P_MOM,
    PERM_COL_I_OUT,
    PERM_HEADERS,
)
from screens.cc_consumption.utils import fmt


@dataclass
class PermanentRow:
    comp_id: str
    gab_label: str
    tag: str
    desc: str
    p_total: float
    pct: float
    p_perm: float
    p_mom: float
    i_perm: float
    i_out: float


class PermanentesTableLogic:
    """Pure logic holder for Permanentes rows."""

    def __init__(self) -> None:
        self._rows: List[PermanentRow] = []

    @staticmethod
    def _calc_row(p_total: float, pct: float, vmin: float) -> tuple[float, float, float, float]:
        pct = max(0.0, min(100.0, float(pct)))
        p_perm = float(p_total) * (pct / 100.0)
        p_mom = max(0.0, float(p_total) * ((100.0 - pct) / 100.0))
        if vmin > 0:
            i_perm = p_perm / vmin
            i_out = p_mom / vmin
        else:
            i_perm = 0.0
            i_out = 0.0
        return p_perm, p_mom, i_perm, i_out

    def set_items(
        self,
        items: List[Any],
        *,
        use_global: bool,
        pct_global: float,
        get_custom_pct: Callable[[dict], float],
        vmin: float,
    ) -> None:
        rows: List[PermanentRow] = []
        for it in items or []:
            comp = getattr(it, "comp", None) or {}
            comp_data = (comp.get("data", {}) or {}) if isinstance(comp, dict) else {}
            p_total = float(getattr(it, "p_eff", 0.0) or 0.0)
            pct = float(pct_global) if use_global else float(get_custom_pct(comp_data))
            p_perm, p_mom, i_perm, i_out = self._calc_row(p_total, pct, vmin)
            rows.append(
                PermanentRow(
                    comp_id=str(getattr(it, "comp_id", "") or ""),
                    gab_label=f"{getattr(it, 'gab_tag', '')} - {getattr(it, 'gab_nombre', '')}".strip(" -"),
                    tag=str(getattr(it, "tag_comp", "") or ""),
                    desc=str(getattr(it, "desc", "") or ""),
                    p_total=p_total,
                    pct=float(pct),
                    p_perm=float(p_perm),
                    p_mom=float(p_mom),
                    i_perm=float(i_perm),
                    i_out=float(i_out),
                )
            )
        self._rows = rows

    def row_count(self) -> int:
        return len(self._rows)

    def row_at(self, row: int) -> Optional[PermanentRow]:
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def set_pct(self, row: int, pct: float, vmin: float) -> bool:
        r = self.row_at(row)
        if r is None:
            return False
        pct = max(0.0, min(100.0, float(pct)))
        if abs(r.pct - pct) < 1e-9:
            return False
        p_perm, p_mom, i_perm, i_out = self._calc_row(r.p_total, pct, vmin)
        r.pct = float(pct)
        r.p_perm = float(p_perm)
        r.p_mom = float(p_mom)
        r.i_perm = float(i_perm)
        r.i_out = float(i_out)
        return True

    def apply_global_pct(self, pct: float, vmin: float) -> None:
        for i in range(len(self._rows)):
            self.set_pct(i, pct, vmin)

    def recalc_all(self, vmin: float) -> None:
        for i in range(len(self._rows)):
            r = self._rows[i]
            self.set_pct(i, r.pct, vmin)


if QtCore is not None:

    class PermanentesTableModel(QtCore.QAbstractTableModel):
        """QAbstractTableModel for CC Permanentes."""

        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self._logic = PermanentesTableLogic()
            self._use_global = True
            self._vmin = 0.0

        def set_use_global(self, use_global: bool) -> None:
            self._use_global = bool(use_global)

        def set_items(self, items: List[Any], *, use_global: bool, pct_global: float, get_custom_pct: Callable[[dict], float], vmin: float) -> None:
            self.beginResetModel()
            self._use_global = bool(use_global)
            self._vmin = float(vmin or 0.0)
            self._logic.set_items(
                items,
                use_global=use_global,
                pct_global=pct_global,
                get_custom_pct=get_custom_pct,
                vmin=self._vmin,
            )
            self.endResetModel()

        def rowCount(self, parent=QtCore.QModelIndex()) -> int:
            return 0 if parent.isValid() else self._logic.row_count()

        def columnCount(self, parent=QtCore.QModelIndex()) -> int:
            return 0 if parent.isValid() else len(PERM_HEADERS)

        def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):
            if role != QtCore.Qt.DisplayRole:
                return None
            if orientation == QtCore.Qt.Horizontal:
                try:
                    return PERM_HEADERS[section]
                except Exception:
                    return None
            return str(section + 1)

        def flags(self, index: QtCore.QModelIndex):
            if not index.isValid():
                return QtCore.Qt.NoItemFlags
            flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
            if index.column() == PERM_COL_PCT and not self._use_global:
                flags |= QtCore.Qt.ItemIsEditable
            return flags

        def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
            if not index.isValid():
                return None
            row = self._logic.row_at(index.row())
            if row is None:
                return None

            if role not in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
                return None

            col = index.column()
            if col == PERM_COL_GAB:
                return row.gab_label
            if col == PERM_COL_TAG:
                return row.tag
            if col == PERM_COL_DESC:
                return row.desc
            if col == PERM_COL_PW:
                return float(row.p_total) if role == QtCore.Qt.EditRole else fmt(row.p_total)
            if col == PERM_COL_PCT:
                return float(row.pct) if role == QtCore.Qt.EditRole else fmt(row.pct)
            if col == PERM_COL_P_PERM:
                return float(row.p_perm) if role == QtCore.Qt.EditRole else fmt(row.p_perm)
            if col == PERM_COL_P_MOM:
                return float(row.p_mom) if role == QtCore.Qt.EditRole else fmt(row.p_mom)
            if col == PERM_COL_I:
                return float(row.i_perm) if role == QtCore.Qt.EditRole else fmt(row.i_perm)
            if col == PERM_COL_I_OUT:
                return float(row.i_out) if role == QtCore.Qt.EditRole else fmt(row.i_out)
            return None

        def setData(self, index: QtCore.QModelIndex, value, role: int = QtCore.Qt.EditRole) -> bool:
            if not index.isValid():
                return False
            if index.column() != PERM_COL_PCT:
                return False
            if role != QtCore.Qt.EditRole:
                return False
            try:
                pct = float(str(value).replace(",", "."))
            except Exception:
                return False
            if pct < 0.0:
                pct = 0.0
            if pct > 100.0:
                pct = 100.0
            row = index.row()
            changed = self._logic.set_pct(row, pct, vmin=self._vmin)
            if changed:
                left = self.index(row, PERM_COL_PCT)
                right = self.index(row, PERM_COL_I_OUT)
                self.dataChanged.emit(left, right, [QtCore.Qt.DisplayRole])
            return changed

        def set_row_pct(self, row: int, pct: float, vmin: float) -> bool:
            self._vmin = float(vmin or 0.0)
            changed = self._logic.set_pct(row, pct, vmin)
            if changed:
                left = self.index(row, PERM_COL_PCT)
                right = self.index(row, PERM_COL_I_OUT)
                self.dataChanged.emit(left, right, [QtCore.Qt.DisplayRole])
            return changed

        def apply_global_pct(self, pct: float, vmin: float) -> None:
            self._vmin = float(vmin or 0.0)
            self._logic.apply_global_pct(pct, self._vmin)
            if self._logic.row_count() > 0:
                left = self.index(0, PERM_COL_PCT)
                right = self.index(self._logic.row_count() - 1, PERM_COL_I_OUT)
                self.dataChanged.emit(left, right, [QtCore.Qt.DisplayRole])

        def recalc_all(self, vmin: float) -> None:
            self._vmin = float(vmin or 0.0)
            self._logic.recalc_all(self._vmin)
            if self._logic.row_count() > 0:
                left = self.index(0, PERM_COL_P_PERM)
                right = self.index(self._logic.row_count() - 1, PERM_COL_I_OUT)
                self.dataChanged.emit(left, right, [QtCore.Qt.DisplayRole])

        def get_row(self, row: int) -> Optional[PermanentRow]:
            return self._logic.row_at(row)

        def sort(self, column: int, order: QtCore.Qt.SortOrder = QtCore.Qt.AscendingOrder) -> None:
            reverse = order == QtCore.Qt.DescendingOrder
            text_cols = {PERM_COL_GAB, PERM_COL_TAG, PERM_COL_DESC}
            numeric_cols = {
                PERM_COL_PW,
                PERM_COL_PCT,
                PERM_COL_P_PERM,
                PERM_COL_P_MOM,
                PERM_COL_I,
                PERM_COL_I_OUT,
            }
            if column not in text_cols and column not in numeric_cols:
                return

            def key_fn(r: PermanentRow):
                if column == PERM_COL_GAB:
                    return (r.gab_label or "").casefold()
                if column == PERM_COL_TAG:
                    return (r.tag or "").casefold()
                if column == PERM_COL_DESC:
                    return (r.desc or "").casefold()
                if column == PERM_COL_PW:
                    return float(r.p_total or 0.0)
                if column == PERM_COL_PCT:
                    return float(r.pct or 0.0)
                if column == PERM_COL_P_PERM:
                    return float(r.p_perm or 0.0)
                if column == PERM_COL_P_MOM:
                    return float(r.p_mom or 0.0)
                if column == PERM_COL_I:
                    return float(r.i_perm or 0.0)
                if column == PERM_COL_I_OUT:
                    return float(r.i_out or 0.0)
                return 0.0

            self.layoutAboutToBeChanged.emit()
            self._logic._rows.sort(key=key_fn, reverse=reverse)
            self.layoutChanged.emit()

else:

    class PermanentesTableModel:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("PyQt5 is required to use PermanentesTableModel")
