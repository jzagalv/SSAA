# -*- coding: utf-8 -*-
"""Selection tables presenter for Bank/Charger screen.

Low-risk refactor: keeps rendering/validation logic in one place, outside the main screen module.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem
from ui.theme import get_theme_token


class SelectionTablesPresenter:
    """Renders and validates bank/charger selection tables.

    It works over the existing QTableWidget instances owned by the screen:
      - screen.tbl_sel_bank
      - screen.tbl_sel_charger

    The screen remains the source of truth for:
      - screen._get_bc_bundle()
      - screen._paint_cell(...)
      - screen._cycle_sort_key(...) (elsewhere)
    """

    def __init__(self, screen):
        self.screen = screen

    # ----------------------------
    # Table helpers (moved from screen)
    # ----------------------------
    @staticmethod
    def clear_table(table: QTableWidget):
        table.setRowCount(0)
        table.clearSpans()

    @staticmethod
    def add_section(table: QTableWidget, title: str) -> int:
        r = table.rowCount()
        table.insertRow(r)
        table.setSpan(r, 0, 1, 2)

        it = QTableWidgetItem(title)
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)

        font = it.font()
        font.setBold(True)
        it.setFont(font)

        # Estilo tipo Excel (azul y texto blanco)
        it.setBackground(QColor(get_theme_token("BRAND", "#204058")))
        it.setForeground(QColor(get_theme_token("ON_DARK", "#FFFFFF")))

        table.setItem(r, 0, it)
        return r

    @staticmethod
    def add_row(table: QTableWidget, label: str, value: str):
        r = table.rowCount()
        table.insertRow(r)
        itL = QTableWidgetItem(label)
        itL.setFlags(itL.flags() & ~Qt.ItemIsEditable)
        itV = QTableWidgetItem(value)
        itV.setFlags(itV.flags() & ~Qt.ItemIsEditable)
        table.setItem(r, 0, itL)
        table.setItem(r, 1, itV)

    # ----------------------------
    # Public API used by controller
    # ----------------------------
    def update(self):
        scr = self.screen

        bundle = scr._get_bc_bundle()

        bank = bundle.bank
        charger = bundle.charger
        missing = bundle.missing_kt_keys
        ah_com = bundle.ah_commercial_str
        i_ch_com = bundle.i_charger_commercial_str

        # --- GUARD CLAUSE: si falta info crítica, no hay banco/cargador ---
        if bank is None or charger is None:
            # Limpia tablas
            self.clear_table(scr.tbl_sel_bank)
            self.add_section(scr.tbl_sel_bank, "Selección Banco de Baterías")
            self.add_row(scr.tbl_sel_bank, "Estado", "Datos incompletos (no se puede calcular)")
            scr.tbl_sel_bank.resizeRowsToContents()

            self.clear_table(scr.tbl_sel_charger)
            self.add_section(scr.tbl_sel_charger, "Selección Cargador")
            self.add_row(scr.tbl_sel_charger, "Estado", "Datos incompletos (no se puede calcular)")
            scr.tbl_sel_charger.resizeRowsToContents()
            return

        # -----------------------
        # Banco de baterías
        # -----------------------
        self.clear_table(scr.tbl_sel_bank)
        self.add_section(scr.tbl_sel_bank, "Selección Banco de Baterías")

        # Datos del banco (resultado de selección)
        # Nota: bank es BankSelectionResult (domain/selection.py)
        self.add_row(scr.tbl_sel_bank, "Base Ah (máx sección + RND)", f"{getattr(bank, 'base_ah', 0.0):.2f}")
        self.add_row(scr.tbl_sel_bank, "Sección crítica", f"{getattr(bank, 'critical_section', '—')}")
        self.add_row(scr.tbl_sel_bank, "K2", f"{getattr(bank, 'k2', 0.0):.3f}")
        self.add_row(scr.tbl_sel_bank, "Margen", f"{getattr(bank, 'margen', 0.0):.3f}")
        self.add_row(scr.tbl_sel_bank, "Envejecimiento", f"{getattr(bank, 'enve', 0.0):.3f}")
        self.add_row(scr.tbl_sel_bank, "Factor total", f"{getattr(bank, 'factor_total', 0.0):.3f}")
        self.add_row(scr.tbl_sel_bank, "Ah requerido", f"{getattr(bank, 'ah_required', 0.0):.2f}")

        # Missing Kt keys
        if missing:
            self.add_row(scr.tbl_sel_bank, "Advertencia", "Faltan Kt para: " + ", ".join(missing))

        # Capacidad comercial editable
        r = scr.tbl_sel_bank.rowCount()
        self.add_row(scr.tbl_sel_bank, "Capacidad Comercial [Ah]", ah_com)
        it = scr.tbl_sel_bank.item(r, 1)
        if it:
            it.setFlags(it.flags() | Qt.ItemIsEditable)
            scr._paint_cell(it, "editable")

        scr.tbl_sel_bank.resizeRowsToContents()

        # -----------------------
        # Cargador
        # -----------------------
        self.clear_table(scr.tbl_sel_charger)
        self.add_section(scr.tbl_sel_charger, "Selección Cargador")

        # Datos del cargador (resultado de selección)
        # Nota: charger es ChargerSelectionResult (domain/selection.py)
        self.add_row(scr.tbl_sel_charger, "I permanente (L1) [A]", f"{getattr(charger, 'i_perm', 0.0):.2f}")
        self.add_row(scr.tbl_sel_charger, "Tiempo recarga [h]", f"{getattr(charger, 't_rec_h', 0.0):.2f}")
        self.add_row(scr.tbl_sel_charger, "K pérdidas", f"{getattr(charger, 'k_loss', 0.0):.3f}")
        self.add_row(scr.tbl_sel_charger, "K altitud", f"{getattr(charger, 'k_alt', 0.0):.3f}")
        self.add_row(scr.tbl_sel_charger, "K temperatura", f"{getattr(charger, 'k_temp', 0.0):.3f}")
        self.add_row(scr.tbl_sel_charger, "K seguridad", f"{getattr(charger, 'k_seg', 0.0):.3f}")
        self.add_row(scr.tbl_sel_charger, "I calculada [A]", f"{getattr(charger, 'i_calc', 0.0):.2f}")
        self.add_row(scr.tbl_sel_charger, "V nominal [V]", f"{getattr(charger, 'v_nom', 0.0):.2f}")
        self.add_row(scr.tbl_sel_charger, "Eficiencia", f"{getattr(charger, 'eff', 0.0):.3f}")
        self.add_row(scr.tbl_sel_charger, "P CC [W]", f"{getattr(charger, 'p_cc_w', 0.0):.1f}")
        self.add_row(scr.tbl_sel_charger, "P CA [W]", f"{getattr(charger, 'p_ca_w', 0.0):.1f}")

        # Capacidad comercial editable
        r2 = scr.tbl_sel_charger.rowCount()
        self.add_row(scr.tbl_sel_charger, "Capacidad Comercial [A]", i_ch_com)
        it2 = scr.tbl_sel_charger.item(r2, 1)
        if it2:
            it2.setFlags(it2.flags() | Qt.ItemIsEditable)
            scr._paint_cell(it2, "editable")

        scr.tbl_sel_charger.resizeRowsToContents()

    def validate(self):
        scr = self.screen

        # Banco: comercial >= Ah requerido
        req: Optional[float] = None
        com: Optional[float] = None
        for r in range(scr.tbl_sel_bank.rowCount()):
            l = scr.tbl_sel_bank.item(r, 0)
            v = scr.tbl_sel_bank.item(r, 1)
            if not l or not v:
                continue
            if l.text().strip() in ("Ah requerido", "Ah requerido [Ah]"):
                try:
                    req = float(v.text().replace(",", "."))
                except Exception:
                    req = None
            if l.text().strip() in ("Capacidad Comercial", "Capacidad Comercial [Ah]"):
                try:
                    com = float(v.text().replace(",", "."))
                except Exception:
                    com = None
                if v.flags() & Qt.ItemIsEditable:
                    scr._paint_cell(v, "editable")
        if req is not None and com is not None and com < req:
            for r in range(scr.tbl_sel_bank.rowCount()):
                l = scr.tbl_sel_bank.item(r, 0)
                v = scr.tbl_sel_bank.item(r, 1)
                if l and v and l.text().strip() in ("Capacidad Comercial", "Capacidad Comercial [Ah]"):
                    scr._paint_cell(v, "invalid")

        # Cargador: comercial >= I calculada
        req = None
        com = None
        for r in range(scr.tbl_sel_charger.rowCount()):
            l = scr.tbl_sel_charger.item(r, 0)
            v = scr.tbl_sel_charger.item(r, 1)
            if not l or not v:
                continue
            if l.text().strip() in ("I calculada [A]", "I calculada"):
                try:
                    req = float(v.text().replace(",", "."))
                except Exception:
                    req = None
            if l.text().strip() in ("Capacidad Comercial", "Capacidad Comercial [Ah]", "Capacidad Comercial [A]"):
                try:
                    com = float(v.text().replace(",", "."))
                except Exception:
                    com = None
                if v.flags() & Qt.ItemIsEditable:
                    scr._paint_cell(v, "editable")
        if req is not None and com is not None and com < req:
            for r in range(scr.tbl_sel_charger.rowCount()):
                l = scr.tbl_sel_charger.item(r, 0)
                v = scr.tbl_sel_charger.item(r, 1)
                if l and v and l.text().strip() in ("Capacidad Comercial", "Capacidad Comercial [Ah]", "Capacidad Comercial [A]"):
                    scr._paint_cell(v, "invalid")
