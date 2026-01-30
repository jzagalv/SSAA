# -*- coding: utf-8 -*-
"""Perfil de cargas (tbl_cargas) presenter.

Aísla la manipulación de la tabla de perfil de cargas (render, RO/editable y autocalculados)
para reducir el tamaño de bank_charger_screen.py.

El cálculo sigue viviendo en domain/* y se invoca vía métodos helper del screen.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableWidgetItem

from domain.cc_consumption import compute_momentary_from_permanents

CODE_L1 = "L1"
CODE_LAL = "L(al)"
CODE_LMOM_AUTO = "L2"
DESC_LMOM_AUTO = "Carga Momentáneas Equipos C&P"


class ProfileTablePresenter:
    def __init__(self, screen):
        self.screen = screen

    def load_from_model(self) -> None:
        scr = self.screen
        proyecto = getattr(scr.data_model, "proyecto", {}) or {}
        perfil = proyecto.get("perfil_cargas", []) or []
        if not perfil:
            return

        scr._updating = True
        try:
            scr.tbl_cargas.setRowCount(0)
            for fila in perfil:
                item = str(fila.get("item", "") or "").strip()
                desc = str(fila.get("desc", "") or "").strip()
                if item == "A1":
                    item = "L1"
                if item == "AL":
                    item = "L(al)"

                p = fila.get("p", "")
                i = fila.get("i", "")
                t0 = fila.get("t_inicio", "")
                dur = fila.get("duracion", "")

                r = scr.tbl_cargas.rowCount()
                scr.tbl_cargas.insertRow(r)
                for c, v in enumerate([item, desc, p, i, t0, dur]):
                    scr.tbl_cargas.setItem(r, c, QTableWidgetItem("" if v is None else str(v)))

            def has_code(code: str) -> bool:
                for rr in range(scr.tbl_cargas.rowCount()):
                    it = scr.tbl_cargas.item(rr, 0)
                    if it and it.text().strip() == code:
                        return True
                return False

            if not has_code("L1"):
                scr.tbl_cargas.insertRow(0)
                scr.tbl_cargas.setItem(0, 0, QTableWidgetItem("L1"))
                scr.tbl_cargas.setItem(0, 1, QTableWidgetItem("Cargas Permanentes"))
                for c in range(2, 6):
                    scr.tbl_cargas.setItem(0, c, QTableWidgetItem("—"))
                scr.tbl_cargas.setItem(0, 4, QTableWidgetItem("0"))

            if not has_code("L(al)"):
                scr.tbl_cargas.insertRow(scr.tbl_cargas.rowCount())
                r = scr.tbl_cargas.rowCount() - 1
                scr.tbl_cargas.setItem(r, 0, QTableWidgetItem("L(al)"))
                scr.tbl_cargas.setItem(r, 1, QTableWidgetItem("Cargas Aleatorias"))
                for c in range(2, 6):
                    scr.tbl_cargas.setItem(r, c, QTableWidgetItem("—"))

            self.apply_editability()
        finally:
            scr._updating = False

    def fill_defaults(self, save_to_model: bool = True) -> None:
        scr = self.screen
        scr._updating = True
        try:
            scr.tbl_cargas.setRowCount(0)
            scr.tbl_cargas.setRowCount(2)

            scr.tbl_cargas.setItem(0, 0, QTableWidgetItem(CODE_L1))
            scr.tbl_cargas.setItem(0, 1, QTableWidgetItem("Cargas Permanentes"))
            for c in range(2, 6):
                scr.tbl_cargas.setItem(0, c, QTableWidgetItem("—"))
            scr.tbl_cargas.setItem(0, 4, QTableWidgetItem("0"))

            scr.tbl_cargas.setItem(1, 0, QTableWidgetItem(CODE_LAL))
            scr.tbl_cargas.setItem(1, 1, QTableWidgetItem("Cargas Aleatorias"))
            for c in range(2, 6):
                scr.tbl_cargas.setItem(1, c, QTableWidgetItem("—"))

            self.apply_editability()
        finally:
            scr._updating = False

        self.refresh_autocalc()
        scr.tbl_cargas.resizeRowsToContents()
        if save_to_model:
            scr._save_perfil_cargas_to_model()

    def apply_editability(self) -> None:
        scr = self.screen
        for r in range(scr.tbl_cargas.rowCount()):
            it = scr.tbl_cargas.item(r, 0)
            code = it.text().strip() if it else ""
            code_n = scr._norm_code(code)
            desc = scr.tbl_cargas.item(r, 1).text().strip() if scr.tbl_cargas.item(r, 1) else ""

            for c in range(scr.tbl_cargas.columnCount()):
                cell = scr.tbl_cargas.item(r, c)
                if cell is None:
                    cell = QTableWidgetItem("")
                    scr.tbl_cargas.setItem(r, c, cell)
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)

            if code_n == scr._norm_code(CODE_LAL):
                for c in (4, 5):
                    scr.tbl_cargas.item(r, c).setFlags(scr.tbl_cargas.item(r, c).flags() | Qt.ItemIsEditable)
            elif code_n == scr._norm_code(CODE_LMOM_AUTO) and desc == DESC_LMOM_AUTO:
                for c in (4, 5):
                    scr.tbl_cargas.item(r, c).setFlags(scr.tbl_cargas.item(r, c).flags() | Qt.ItemIsEditable)
            elif code_n not in (scr._norm_code(CODE_L1), scr._norm_code(CODE_LAL)) and code:
                for c in (1, 4, 5):
                    scr.tbl_cargas.item(r, c).setFlags(scr.tbl_cargas.item(r, c).flags() | Qt.ItemIsEditable)

    def row_index_of_code(self, code: str) -> int:
        scr = self.screen
        code_n = scr._norm_code(code)
        for r in range(scr.tbl_cargas.rowCount()):
            it = scr.tbl_cargas.item(r, 0)
            if it and scr._norm_code(it.text()) == code_n:
                return r
        return -1

    def refresh_autocalc(self) -> None:
        scr = self.screen
        if scr._updating:
            return

        scr._updating = True
        try:
            vmin = scr._get_vmin_cc()
            if vmin <= 0:
                vmin = 1.0

            p_perm, p_ale = scr._compute_cc_profile_totals()

            try:
                proyecto = getattr(scr.data_model, "proyecto", {}) or {}
                gabinetes = scr._get_model_gabinetes()
                p_mom_auto = float(compute_momentary_from_permanents(proyecto=proyecto, gabinetes=gabinetes) or 0.0)
            except Exception:
                p_mom_auto = 0.0

            # El controller decide crear/eliminar L2 automático; acá solo refrescamos valores.
            scr._ensure_auto_momentary_load_in_profile(save_to_model=False)

            r_l1 = self.row_index_of_code(CODE_L1)
            if r_l1 >= 0:
                scr.tbl_cargas.item(r_l1, 2).setText(f"{p_perm:.2f}")
                scr.tbl_cargas.item(r_l1, 3).setText(f"{(p_perm / vmin):.2f}")

            r_lal = self.row_index_of_code(CODE_LAL)
            if r_lal >= 0:
                scr.tbl_cargas.item(r_lal, 2).setText(f"{p_ale:.2f}")
                scr.tbl_cargas.item(r_lal, 3).setText(f"{(p_ale / vmin):.2f}")

            # Actualizar L2 automático si existe
            r_l2a = -1
            for r in range(scr.tbl_cargas.rowCount()):
                code_it = scr.tbl_cargas.item(r, 0)
                desc_it = scr.tbl_cargas.item(r, 1)
                if not code_it or not desc_it:
                    continue
                if scr._norm_code(code_it.text()) == scr._norm_code(CODE_LMOM_AUTO) and desc_it.text().strip() == DESC_LMOM_AUTO:
                    r_l2a = r
                    break

            if r_l2a >= 0:
                scr.tbl_cargas.item(r_l2a, 2).setText(f"{p_mom_auto:.2f}")
                scr.tbl_cargas.item(r_l2a, 3).setText(f"{(p_mom_auto / vmin):.2f}")

            self.apply_editability()
        finally:
            scr._updating = False
