# -*- coding: utf-8 -*-
"""
UI helpers for CC Consumption screen.

This module contains:
- Column indices and headers (single source of truth for the screen tables)
- Factory helpers to create configured QTableWidget instances
- Render helpers to populate tables from domain items (no business logic)
"""
from __future__ import annotations

from typing import Callable, Iterable, Optional, Dict

from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QComboBox
from PyQt5.QtCore import Qt

# ----------------------------
# Column indices (no magic numbers)
# ----------------------------

# Permanentes
PERM_COL_GAB = 0
PERM_COL_TAG = 1
PERM_COL_DESC = 2
PERM_COL_PW = 3          # P total [W]
PERM_COL_PCT = 4         # % Utilización
PERM_COL_P_PERM = 5      # P permanente [W]
PERM_COL_I = 6           # I permanente [A]
PERM_COL_P_MOM = 7       # P momentánea [W]
PERM_COL_I_OUT = 8       # I fuera % [A]

PERM_HEADERS = [
    "Gabinete",
    "TAG",
    "Descripción",
    "P total [W]",
    "% Utilización",
    "P permanente [W]",
    "I permanente [A]",
    "P momentánea [W]",
    "I fuera % [A]",
]

# Momentáneos
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
    "Descripción",
    "P efectiva [W]",
    "I [A]",
    "Incluir",
    "Escenario",
]

# Resumen de escenarios
MOMR_COL_ESC = 0
MOMR_COL_DESC = 1
MOMR_COL_PT = 2
MOMR_COL_IT = 3

MOMR_HEADERS = [
    "Escenario",
    "Descripción",
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
    "Descripción",
    "P efectiva [W]",
    "I [A]",
]

# ----------------------------
# Table factories
# ----------------------------

def _mk_table(parent, cols: int, headers: list) -> QTableWidget:
    tbl = QTableWidget(0, cols, parent)
    tbl.setHorizontalHeaderLabels(headers)
    tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    tbl.verticalHeader().setVisible(False)
    tbl.setAlternatingRowColors(True)
    tbl.setSelectionBehavior(QTableWidget.SelectRows)
    tbl.setSelectionMode(QTableWidget.SingleSelection)
    return tbl

def create_perm_table(parent) -> QTableWidget:
    tbl = _mk_table(parent, 9, PERM_HEADERS)
    # Consistente con el screen: permite editar % (controlado por lógica externa)
    tbl.setEditTriggers(QTableWidget.AllEditTriggers)
    return tbl

def create_mom_table(parent) -> QTableWidget:
    tbl = _mk_table(parent, 7, MOM_HEADERS)
    tbl.setEditTriggers(QTableWidget.AllEditTriggers)
    return tbl

def create_mom_summary_table(parent) -> QTableWidget:
    tbl = _mk_table(parent, 4, MOMR_HEADERS)
    tbl.setEditTriggers(QTableWidget.AllEditTriggers)
    return tbl

def create_rand_table(parent) -> QTableWidget:
    tbl = _mk_table(parent, 6, ALE_HEADERS)
    tbl.setEditTriggers(QTableWidget.AllEditTriggers)
    return tbl

# ----------------------------
# Render helpers (UI-only)
# ----------------------------

def load_permanentes(
    table: QTableWidget,
    items: Iterable,
    *,
    usar_global: bool,
    pct_global: float,
    get_custom_pct: Callable[[dict], float],
    update_row_cb: Optional[Callable[[int], None]] = None,
) -> None:
    """
    Populate permanentes table.

    Parameters
    ----------
    items:
        Iterable of CCItem-like objects.
    get_custom_pct:
        Called with comp_data (dict) and must return pct (float).
    update_row_cb:
        Called after a row is created (useful to compute derived columns).
    """
    table.blockSignals(True)
    table.setRowCount(0)

    for it in items:
        row = table.rowCount()
        table.insertRow(row)

        gab_label = f"{getattr(it, 'gab_tag', '')} - {getattr(it, 'gab_nombre', '')}".strip(" -")

        it_gab = QTableWidgetItem(gab_label)
        it_gab.setFlags(it_gab.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, PERM_COL_GAB, it_gab)

        it_tag = QTableWidgetItem(getattr(it, "tag_comp", ""))
        it_tag.setData(Qt.UserRole, getattr(it, "comp_id", ""))
        it_tag.setFlags(it_tag.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, PERM_COL_TAG, it_tag)

        it_desc = QTableWidgetItem(getattr(it, "desc", ""))
        it_desc.setFlags(it_desc.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, PERM_COL_DESC, it_desc)

        p_eff = float(getattr(it, "p_eff", 0.0) or 0.0)
        it_pw = QTableWidgetItem("" if p_eff == 0 else f"{p_eff:.2f}")
        it_pw.setFlags(it_pw.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, PERM_COL_PW, it_pw)

        comp_data = (getattr(it, "comp", None) or {}).get("data", {}) or {}
        pct_val = float(pct_global) if usar_global else float(get_custom_pct(comp_data))
        pct_val = max(0.0, min(100.0, pct_val))
        it_pct = QTableWidgetItem(f"{pct_val:.2f}")
        table.setItem(row, PERM_COL_PCT, it_pct)

        # Inicializar columnas calculadas (bloqueadas)
        for col in (PERM_COL_P_PERM, PERM_COL_P_MOM, PERM_COL_I, PERM_COL_I_OUT):
            cell = QTableWidgetItem("0.00")
            cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, col, cell)

        if update_row_cb:
            update_row_cb(row)

    table.blockSignals(False)


def load_momentaneos(
    table: QTableWidget,
    items: Iterable,
    *,
    n_escenarios: int,
) -> None:
    """Fill the 'Momentáneos' table.

    Restores persisted flags from domain.CCItem:
    - mom_incluir
    - mom_escenario

    Uses a QComboBox for the 'Escenario' column so the screen can rebuild options.
    """
    table.blockSignals(True)
    table.setRowCount(0)

    # Defensive clamp
    n_escenarios = int(n_escenarios or 1)
    if n_escenarios < 1:
        n_escenarios = 1

    for it in items:
        row = table.rowCount()
        table.insertRow(row)

        gab_label = f"{getattr(it, 'gab_tag', '')} - {getattr(it, 'gab_nombre', '')}".strip(" -")
        it_gab = QTableWidgetItem(gab_label)
        it_gab.setFlags(it_gab.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, MOM_COL_GAB, it_gab)

        it_tag = QTableWidgetItem(getattr(it, "tag_comp", ""))
        it_tag.setData(Qt.UserRole, getattr(it, "comp_id", ""))
        it_tag.setFlags(it_tag.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, MOM_COL_TAG, it_tag)

        it_desc = QTableWidgetItem(getattr(it, "desc", ""))
        it_desc.setFlags(it_desc.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, MOM_COL_DESC, it_desc)

        p_eff = float(getattr(it, "p_eff", 0.0) or 0.0)
        it_p = QTableWidgetItem("" if p_eff == 0 else f"{p_eff:.2f}")
        it_p.setFlags(it_p.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, MOM_COL_PEFF, it_p)

        # I is calculated by the screen (depends on Vmin)
        it_i = QTableWidgetItem("0.00")
        it_i.setFlags(it_i.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, MOM_COL_I, it_i)

        # Persisted include flag
        mom_incluir = bool(getattr(it, "mom_incluir", True))
        it_inc = QTableWidgetItem("")
        it_inc.setFlags(it_inc.flags() | Qt.ItemIsUserCheckable)
        it_inc.setCheckState(Qt.Checked if mom_incluir else Qt.Unchecked)
        table.setItem(row, MOM_COL_INCLUIR, it_inc)

        # Scenario as combobox
        mom_esc = int(getattr(it, "mom_escenario", 1) or 1)
        if mom_esc < 1:
            mom_esc = 1
        if mom_esc > n_escenarios:
            mom_esc = n_escenarios

        combo = QComboBox()
        for n in range(1, n_escenarios + 1):
            combo.addItem(str(n), n)
        idx = combo.findData(mom_esc)
        combo.setCurrentIndex(0 if idx < 0 else idx)
        table.setCellWidget(row, MOM_COL_ESC, combo)

    table.blockSignals(False)



def load_aleatorios(
    table: QTableWidget,
    items: Iterable,
) -> None:
    table.blockSignals(True)
    table.setRowCount(0)

    for it in items:
        row = table.rowCount()
        table.insertRow(row)

        it_sel = QTableWidgetItem("")
        it_sel.setFlags(it_sel.flags() | Qt.ItemIsUserCheckable)
        it_sel.setCheckState(Qt.Unchecked)
        table.setItem(row, ALE_COL_SEL, it_sel)

        gab_label = f"{getattr(it, 'gab_tag', '')} - {getattr(it, 'gab_nombre', '')}".strip(" -")
        it_gab = QTableWidgetItem(gab_label)
        it_gab.setFlags(it_gab.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, ALE_COL_GAB, it_gab)

        it_tag = QTableWidgetItem(getattr(it, "tag_comp", ""))
        it_tag.setData(Qt.UserRole, getattr(it, "comp_id", ""))
        it_tag.setFlags(it_tag.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, ALE_COL_TAG, it_tag)

        it_desc = QTableWidgetItem(getattr(it, "desc", ""))
        it_desc.setFlags(it_desc.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, ALE_COL_DESC, it_desc)

        p_eff = float(getattr(it, "p_eff", 0.0) or 0.0)
        it_p = QTableWidgetItem("" if p_eff == 0 else f"{p_eff:.2f}")
        it_p.setFlags(it_p.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, ALE_COL_PEFF, it_p)

        it_i = QTableWidgetItem("0.00")
        it_i.setFlags(it_i.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, ALE_COL_I, it_i)

    table.blockSignals(False)
