# -*- coding: utf-8 -*-
"""Table schema helpers for CC Consumption UI (QTableWidget)."""
from __future__ import annotations

from typing import Any, Dict

try:
    from PyQt5.QtCore import Qt  # type: ignore
except Exception:  # pragma: no cover
    class _QtFallback:
        UserRole = 0x0100
        Checked = 2
        Unchecked = 0
    Qt = _QtFallback()  # type: ignore

# ----------------------------
# Column indices (single source of truth)
# ----------------------------

# Permanentes
PERM_COL_GAB = 0
PERM_COL_TAG = 1
PERM_COL_DESC = 2
PERM_COL_PW = 3          # P total [W]
PERM_COL_PCT = 4         # % Utilizacion
PERM_COL_P_PERM = 5      # P permanente [W]
PERM_COL_I = 6           # I permanente [A]
PERM_COL_P_MOM = 7       # P momentanea [W]
PERM_COL_I_OUT = 8       # I fuera % [A]

PERM_HEADERS = [
    "Gabinete",
    "TAG",
    "Descripcion",
    "P total [W]",
    "% Utilizacion",
    "P permanente [W]",
    "I permanente [A]",
    "P momentanea [W]",
    "I fuera % [A]",
]

# Momentaneos
MOM_COL_GAB = 0
MOM_COL_TAG = 1
MOM_COL_DESC = 2
MOM_COL_PEFF = 3
MOM_COL_I = 4
MOM_COL_INCLUIR = 5
MOM_COL_ESC = 6

MOM_HEADERS = [
    "Gabinete",
    "TAG",
    "Descripcion",
    "P efectiva [W]",
    "I [A]",
    "Incluir",
    "Escenario",
]

# Resumen de escenarios
MOMR_COL_ESC = 0
MOMR_COL_PERM = 1
MOMR_COL_DESC = 2
MOMR_COL_PT = 3
MOMR_COL_IT = 4
# Compat alias (código previo)
MOMR_COL_USE = MOMR_COL_PERM

MOMR_HEADERS = [
    "Escenario",
    "Incl. perm.",
    "Descripcion",
    "P total [W]",
    "I total [A]",
]

# Aleatorios
ALE_COL_SEL = 0
ALE_COL_GAB = 1
ALE_COL_TAG = 2
ALE_COL_DESC = 3
ALE_COL_PEFF = 4
ALE_COL_I = 5

ALE_HEADERS = [
    "Sel.",
    "Gabinete",
    "TAG",
    "Descripcion",
    "P efectiva [W]",
    "I [A]",
]


def read_perm_row(table, row: int) -> Dict[str, Any]:
    it_tag = table.item(row, PERM_COL_TAG)
    it_pct = table.item(row, PERM_COL_PCT)
    comp_id = it_tag.data(Qt.UserRole) if it_tag else ""
    return {
        "comp_id": comp_id or "",
        "pct_text": it_pct.text() if it_pct else "",
    }


def write_perm_row(table, row: int, data: Dict[str, Any]) -> None:
    if "pct_text" in data:
        it_pct = table.item(row, PERM_COL_PCT)
        if it_pct is not None:
            it_pct.setText(str(data["pct_text"]))


def read_mom_row(table, row: int) -> Dict[str, Any]:
    it_tag = table.item(row, MOM_COL_TAG)
    comp_id = it_tag.data(Qt.UserRole) if it_tag else ""
    it_inc = table.item(row, MOM_COL_INCLUIR)
    incluir = bool(it_inc.checkState() == Qt.Checked) if it_inc else True
    combo = table.cellWidget(row, MOM_COL_ESC)
    esc = combo.currentData() if combo is not None else 1
    return {
        "comp_id": comp_id or "",
        "incluir": bool(incluir),
        "escenario": int(esc or 1),
    }


def write_mom_row(table, row: int, data: Dict[str, Any]) -> None:
    if "incluir" in data:
        it_inc = table.item(row, MOM_COL_INCLUIR)
        if it_inc is not None:
            it_inc.setCheckState(Qt.Checked if data["incluir"] else Qt.Unchecked)
    if "escenario" in data:
        combo = table.cellWidget(row, MOM_COL_ESC)
        if combo is not None:
            idx = combo.findData(int(data["escenario"]))
            combo.setCurrentIndex(0 if idx < 0 else idx)


def read_ale_row(table, row: int) -> Dict[str, Any]:
    it_sel = table.item(row, ALE_COL_SEL)
    selected = bool(it_sel.checkState() == Qt.Checked) if it_sel else False
    it_tag = table.item(row, ALE_COL_TAG)
    comp_id = it_tag.data(Qt.UserRole) if it_tag else ""
    return {
        "comp_id": comp_id or "",
        "selected": selected,
    }


def write_ale_row(table, row: int, data: Dict[str, Any]) -> None:
    if "selected" in data:
        it_sel = table.item(row, ALE_COL_SEL)
        if it_sel is not None:
            it_sel.setCheckState(Qt.Checked if data["selected"] else Qt.Unchecked)
