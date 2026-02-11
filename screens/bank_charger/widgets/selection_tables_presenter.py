# -*- coding: utf-8 -*-
"""Selection tables presenter for Bank/Charger screen."""

from __future__ import annotations

from typing import Callable, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QDoubleSpinBox, QTableWidget, QTableWidgetItem

from ui.theme import get_theme_token


class SelectionTablesPresenter:
    """Renders and validates bank/charger selection tables."""

    def __init__(
        self,
        screen,
        *,
        on_k1_changed: Optional[Callable[[float], None]] = None,
        on_k2_changed: Optional[Callable[[float], None]] = None,
        on_k3_changed: Optional[Callable[[float], None]] = None,
    ):
        self.screen = screen
        self.on_k1_changed = on_k1_changed
        self.on_k2_changed = on_k2_changed
        self.on_k3_changed = on_k3_changed

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
        it.setBackground(QColor(get_theme_token("BRAND", "#204058")))
        it.setForeground(QColor(get_theme_token("ON_DARK", "#FFFFFF")))
        table.setItem(r, 0, it)
        return r

    @staticmethod
    def add_row(table: QTableWidget, label: str, value: str):
        r = table.rowCount()
        table.insertRow(r)
        it_l = QTableWidgetItem(label)
        it_l.setFlags(it_l.flags() & ~Qt.ItemIsEditable)
        it_v = QTableWidgetItem(value)
        it_v.setFlags(it_v.flags() & ~Qt.ItemIsEditable)
        table.setItem(r, 0, it_l)
        table.setItem(r, 1, it_v)

    def _add_factor_spin(
        self,
        table: QTableWidget,
        *,
        label: str,
        value: float,
        callback: Optional[Callable[[float], None]],
    ) -> None:
        r = table.rowCount()
        table.insertRow(r)

        it_l = QTableWidgetItem(label)
        it_l.setFlags(it_l.flags() & ~Qt.ItemIsEditable)
        table.setItem(r, 0, it_l)

        spin = QDoubleSpinBox(table)
        spin.setDecimals(3)
        spin.setSingleStep(0.01)
        spin.setRange(0.5, 2.0)
        spin.setKeyboardTracking(False)
        spin.setValue(float(value or 0.0))
        spin.setProperty("userField", True)
        if callback is not None:
            spin.valueChanged.connect(lambda v, cb=callback: cb(float(v)))
        table.setCellWidget(r, 1, spin)

    def update(self):
        scr = self.screen
        bundle = scr._get_bc_bundle()

        bank = bundle.bank
        charger = bundle.charger
        ah_com = bundle.ah_commercial_str
        i_ch_com = bundle.i_charger_commercial_str
        warnings = list(getattr(bundle, "warnings", []) or [])

        if bank is None or charger is None:
            self.clear_table(scr.tbl_sel_bank)
            self.add_section(scr.tbl_sel_bank, "Selección Banco de Baterías")
            self.add_row(scr.tbl_sel_bank, "Estado", "Datos incompletos (no se puede calcular)")
            scr.tbl_sel_bank.resizeRowsToContents()

            self.clear_table(scr.tbl_sel_charger)
            self.add_section(scr.tbl_sel_charger, "Selección Cargador")
            self.add_row(scr.tbl_sel_charger, "Estado", "Datos incompletos (no se puede calcular)")
            scr.tbl_sel_charger.resizeRowsToContents()
            return

        self.clear_table(scr.tbl_sel_bank)
        self.add_section(scr.tbl_sel_bank, "Selección Banco de Baterías")
        self.add_row(scr.tbl_sel_bank, "Base Ah (máx sección + RND)", f"{getattr(bank, 'base_ah', 0.0):.2f}")
        self.add_row(scr.tbl_sel_bank, "Sección crítica", f"{getattr(bank, 'critical_section', '—')}")
        self._add_factor_spin(
            scr.tbl_sel_bank,
            label="Margen de diseño (K1)",
            value=getattr(bank, "margen", 0.0),
            callback=self.on_k1_changed,
        )
        self._add_factor_spin(
            scr.tbl_sel_bank,
            label="Factor Altitud (K2)",
            value=getattr(bank, "k2", 0.0),
            callback=self.on_k2_changed,
        )
        self._add_factor_spin(
            scr.tbl_sel_bank,
            label="Envejecimiento (K3)",
            value=getattr(bank, "enve", 0.0),
            callback=self.on_k3_changed,
        )
        self.add_row(scr.tbl_sel_bank, "Factor total", f"{getattr(bank, 'factor_total', 0.0):.3f}")
        self.add_row(scr.tbl_sel_bank, "Ah requerido", f"{getattr(bank, 'ah_required', 0.0):.2f}")
        self.add_row(scr.tbl_sel_bank, "Capacidad Comercial [Ah]", ah_com)

        for w in warnings:
            text = str(w or "").strip()
            if text:
                self.add_row(scr.tbl_sel_bank, "Advertencia", text)

        scr.tbl_sel_bank.resizeRowsToContents()

        self.clear_table(scr.tbl_sel_charger)
        self.add_section(scr.tbl_sel_charger, "Selección Cargador")
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
        self.add_row(scr.tbl_sel_charger, "Capacidad Comercial [A]", i_ch_com)

        r2 = scr.tbl_sel_charger.rowCount() - 1
        it2 = scr.tbl_sel_charger.item(r2, 1)
        if it2:
            it2.setFlags(it2.flags() | Qt.ItemIsEditable)
            scr._paint_cell(it2, "editable")

        scr.tbl_sel_charger.resizeRowsToContents()

    def validate(self):
        scr = self.screen

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
