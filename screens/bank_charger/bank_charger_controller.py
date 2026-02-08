# -*- coding: utf-8 -*-
"""Bank Charger controller.

Extracted from bank_charger_screen.py to reduce file size and improve separation.
Low-risk approach: controller holds a reference to the screen and operates on its widgets.
"""

from __future__ import annotations

import math
import os
import re

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from .widgets.selection_tables_presenter import SelectionTablesPresenter
from .widgets.ieee485_table_presenter import IEEE485TablePresenter
from .widgets.summary_table_presenter import SummaryTablePresenter
from .widgets.duty_cycle_table_presenter import DutyCycleTablePresenter
from .widgets.profile_table_presenter import ProfileTablePresenter
from .persistence import BankChargerPersistence
from .update_pipeline import BankChargerUpdatePipeline
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QInputDialog,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
)


from domain.cc_consumption import compute_momentary_from_permanents

# Constants shared with bank_charger_screen
DURACION_MIN_GRAFICA_MIN = 10.0
CODE_L1 = "L1"
CODE_LAL = "L(al)"
CODE_LMOM_AUTO = "L2"
DESC_LMOM_AUTO = "Carga Momentáneas Equipos C&P"


from services.bank_charger_service import compute_and_update_project
from app.base_controller import BaseController
from core.sections import Section


class BankChargerController(BaseController):
    def __init__(self, screen):
        super().__init__(screen=screen, section=Section.BANK_CHARGER)
        self.screen = screen
        self.selection_presenter = SelectionTablesPresenter(screen)
        self.ieee_presenter = IEEE485TablePresenter(screen)
        self.summary_presenter = SummaryTablePresenter(screen)
        self.duty_cycle_presenter = DutyCycleTablePresenter(screen)
        self.profile_presenter = ProfileTablePresenter(screen)

        # Persistencia (proyecto <-> UI)
        self.persistence = BankChargerPersistence(screen)

        # Centralized update sequencing
        self.pipeline = BankChargerUpdatePipeline(screen=screen, controller=self)

    def commit_any_table(self, table: QTableWidget):
        s = self.screen
        if table is None:
            return
        self.safe_call(
            self._commit_any_table_impl,
            table,
            default=None,
            title="Edición",
            user_message="No se pudo confirmar una edición pendiente (best-effort).",
            log_message="commit_any_table failed",
        )

    def _commit_any_table_impl(self, table: QTableWidget):
        # Si hay editor activo, forzamos commit
        editor = QApplication.focusWidget()
        if editor is not None:
            editor.clearFocus()
        table.setFocus(Qt.OtherFocusReason)
        QApplication.processEvents()


    def commit_pending_edits(self):
        scr = self.screen
        # Commit de todas las tablas relevantes (para no perder el editor activo)
        self.commit_any_table(scr.tbl_cargas)
        self.commit_any_table(scr.tbl_ieee)
        self.commit_any_table(scr.tbl_datos)
        self.commit_any_table(scr.tbl_comp)

        # Persistencias (sin pasar por wrappers del screen)
        self.safe_call(
            self.save_perfil_cargas_to_model,
            default=None,
            title="Persistencia",
            user_message="No se pudo guardar el perfil de cargas (best-effort).",
            log_message="save_perfil_cargas_to_model failed",
        )
        self.safe_call(
            self.persist_ieee_kt_to_model,
            default=None,
            title="Persistencia",
            user_message="No se pudo guardar Kt (best-effort).",
            log_message="persist_ieee_kt_to_model failed",
        )


    def schedule_updates(self):
        s = self.screen
        s._chart_timer.start(80)


    def save_perfil_cargas_to_model(self):
        return self.persistence.save_perfil_cargas()


    
    def update_cycle_table(self):
        """Actualiza la tabla Ciclo de trabajo (UI).

        La lógica de render se movió a DutyCycleTablePresenter para mantener el controller liviano.
        """
        return self.duty_cycle_presenter.update()

    def update_profile_chart(self):
        s = self.screen
        det, rnd = s._extract_segments()
        segs_real = det[:]
        if rnd:
            segs_real.append({
                "code": CODE_LAL,
                "I": rnd["I"],
                "t0": rnd["t0"],
                "t1": rnd["t1"],
                "dur": rnd["dur"],
            })

        # Renderiza usando el widget dedicado (Paso 3B)
        s.plot_widget.plot_from_segments(
            segs_real=segs_real,
            sort_key=self.screen._cycle_sort_key,
            periods=(s._cycle_periods_cache or []),
            rnd_cache=getattr(s, "_cycle_random_cache", None),
        )


    def build_ieee485_table_structure(self):
        s = self.screen
        """Aplica estilo, deja tabla preparada. El contenido se genera en _update_ieee485_table()."""
        s.tbl_ieee.blockSignals(True)
        try:
            s.tbl_ieee.setRowCount(0)
        finally:
            s.tbl_ieee.blockSignals(False)
        # por defecto, bloqueamos edición global; luego habilitamos Kt por fila
        s.tbl_ieee.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )


    def persist_ieee_kt_to_model(self):
        return self.persistence.save_ieee485_kt()

    def update_ieee485_table(self):
        """Renderiza la tabla IEEE 485 (UI) desde el duty cycle cache."""
        return self.ieee_presenter.update()




    def update_selection_tables(self):
        return self.selection_presenter.update()
    def validate_selection_tables(self):
        return self.selection_presenter.validate()
    def update_summary_table(self):
        """Tabla resumen de equipos (UI)."""
        return self.summary_presenter.update()


    def reload_from_project(self):
        s = self.screen
        """Recarga datos desde data_model.proyecto (incluye Perfil de cargas guardado)."""
        s._perfil_loaded = False
        s._ieee_loaded = False
        s._seleccion_loaded = False
        s._resumen_loaded = False

        idx = 0
        if getattr(s, "inner_tabs", None) is not None:
            idx = s.inner_tabs.currentIndex()
        self.refresh_bank_charger_inner_tab(idx)

    def _refresh_datos_y_comprobacion(self):
        s = self.screen
        s._updating = True
        try:
            if hasattr(s, "_load_modes_from_project"):
                s._load_modes_from_project()
            s._fill_datos_sistema()
            s._fill_comprobacion()
            s._install_vcell_combo()

            stored = s._proj_value("v_celda_sel_usuario")
            s._user_vcell_sel = None
            if stored:
                idx = s.vcell_combo.findText(stored)
                if idx >= 0:
                    s.vcell_combo.setCurrentIndex(idx)
                try:
                    s._user_vcell_sel = float(str(stored).replace(",", "."))
                except ValueError:
                    s._user_vcell_sel = None
        finally:
            s._updating = False

        if hasattr(s, "_refresh_datos_comp_derived"):
            try:
                s._refresh_datos_comp_derived()
            except Exception:
                import logging
                logging.getLogger(__name__).debug("refresh_datos_comp_derived failed", exc_info=True)

    def _refresh_perfil(self):
        s = self.screen
        s._fill_perfil_cargas(save_to_model=False)
        s._load_perfil_cargas_from_model()
        # Asegurar carga automática L2 (momentáneas derivadas de permanentes), si aplica
        s._ensure_auto_momentary_load_in_profile(save_to_model=False)
        s._refresh_perfil_autocalc()
        s._update_cycle_table()
        s._perfil_loaded = True

    def _refresh_ieee(self):
        s = self.screen
        s._refresh_perfil_autocalc()
        s._update_cycle_table()
        s._build_ieee485_table_structure()
        s._update_ieee485_table()
        s._ieee_loaded = True

    def _refresh_seleccion(self):
        s = self.screen
        s._update_selection_tables()
        s._seleccion_loaded = True

    def _refresh_resumen(self):
        s = self.screen
        s._update_summary_table()
        s._resumen_loaded = True

    def refresh_bank_charger_inner_tab(self, idx: int):
        s = self.screen
        if idx == 0:
            self._refresh_datos_y_comprobacion()
            s._schedule_updates()
            return
        if idx == 1:
            if not getattr(s, "_perfil_loaded", False):
                self._refresh_perfil()
            s._schedule_updates()
            return
        if idx == 2:
            if not getattr(s, "_ieee_loaded", False):
                self._refresh_ieee()
            s._schedule_updates()
            return
        if idx == 3:
            if not getattr(s, "_seleccion_loaded", False):
                self._refresh_seleccion()
            s._schedule_updates()
            return
        if idx == 4:
            if not getattr(s, "_resumen_loaded", False):
                self._refresh_resumen()
            s._schedule_updates()
            return


    def ensure_auto_momentary_load_in_profile(self, save_to_model: bool = True):
        s = self.screen
        """Inserta/actualiza una carga automática en el Perfil de cargas.

        Regla:
        - Si existe potencia momentánea derivada de consumos C.C. permanentes (>0),
          debe existir una fila con código L2 y descripción DESC_LMOM_AUTO.
        - Si el usuario ya tenía una L2, esta se desplaza a L3 (y así sucesivamente).
        - No modifica L1 ni L(al).
        """

        proyecto = getattr(s.data_model, "proyecto", {}) or {}
        gabinetes = s._get_model_gabinetes()

        p_mom = float(compute_momentary_from_permanents(proyecto=proyecto, gabinetes=gabinetes) or 0.0)

        # Si no hay potencia momentánea derivada de permanentes, NO debe existir la carga automática.
        # Además, si hay cargas L>=3 (por ejemplo escenarios) deben correrse hacia abajo para liberar L2.
        if p_mom <= 0:
            row_l2 = s._row_index_of_code(CODE_LMOM_AUTO)
            if row_l2 >= 0:
                desc_existing = (s.tbl_cargas.item(row_l2, 1).text().strip() if s.tbl_cargas.item(row_l2, 1) else "")
                if desc_existing == DESC_LMOM_AUTO:
                    # eliminar la fila automática
                    s._updating = True
                    try:
                        s.tbl_cargas.removeRow(row_l2)
                    finally:
                        s._updating = False

                    # correr L>=3 -> L>=2 (para que el primer escenario pase a ser L2)
                    def parse_l_num(code_text: str):
                        cn = s._norm_code(code_text)
                        if cn.startswith("L") and cn[1:].isdigit():
                            return int(cn[1:])
                        return None

                    nums = []
                    for r in range(s.tbl_cargas.rowCount()):
                        code = s.tbl_cargas.item(r, 0).text().strip() if s.tbl_cargas.item(r, 0) else ""
                        n = parse_l_num(code)
                        if n is not None and n >= 3:
                            nums.append((n, r))

                    # orden ascendente para evitar colisiones al decrementar
                    for n, r in sorted(nums, key=lambda x: x[0]):
                        s._set_text_cell(s.tbl_cargas, r, 0, f"L{n-1}", editable=False)

                    s._apply_perfil_editability()
                    if save_to_model:
                        s._save_perfil_cargas_to_model()

            return

        vmin = s._get_vmin_cc()
        if vmin <= 0:
            vmin = 1.0
        i_mom = p_mom / vmin
        def parse_l_num(code_text: str):
            cn = s._norm_code(code_text)
            if cn.startswith("L") and cn[1:].isdigit():
                return int(cn[1:])
            return None

        # ¿Ya existe una fila L2?
        row_l2 = s._row_index_of_code(CODE_LMOM_AUTO)
        if row_l2 >= 0:
            desc_existing = (s.tbl_cargas.item(row_l2, 1).text().strip() if s.tbl_cargas.item(row_l2, 1) else "")
            if desc_existing != DESC_LMOM_AUTO:
                # L2 es del usuario -> desplazar todas L>=2 una posición hacia arriba
                # (hacerlo desde el máximo para no pisar)
                nums = []
                for r in range(s.tbl_cargas.rowCount()):
                    code = s.tbl_cargas.item(r, 0).text().strip() if s.tbl_cargas.item(r, 0) else ""
                    n = parse_l_num(code)
                    if n is not None and n >= 2:
                        nums.append((n, r))

                # orden descendente por n
                for n, r in sorted(nums, key=lambda x: x[0], reverse=True):
                    s._set_text_cell(s.tbl_cargas, r, 0, f"L{n+1}", editable=False)

                # Recalcular fila L2 después del shift
                row_l2 = s._row_index_of_code(CODE_LMOM_AUTO)

        # Si no existe fila L2 (o se desplazó), insertarla justo después de L1
        if row_l2 < 0:
            row_l1 = s._row_index_of_code(CODE_L1)
            insert_at = (row_l1 + 1) if row_l1 >= 0 else 0

            # Propuesta inicial de tiempos: al final de la autonomía (1 min)
            t_aut = s._get_autonomia_min()
            t0_def = max(0.0, float(t_aut) - 1.0) if (t_aut and float(t_aut) > 0) else None
            dur_def = 1.0 if t0_def is not None else None

            s._updating = True
            try:
                s.tbl_cargas.insertRow(insert_at)
                vals = [
                    CODE_LMOM_AUTO,
                    DESC_LMOM_AUTO,
                    f"{p_mom:.2f}",
                    f"{i_mom:.2f}",
                    (f"{t0_def:.0f}" if t0_def is not None else "—"),
                    (f"{dur_def:.0f}" if dur_def is not None else "—"),
                ]
                for c, v in enumerate(vals):
                    s.tbl_cargas.setItem(insert_at, c, QTableWidgetItem(str(v)))
            finally:
                s._updating = False
        else:
            # Existe y es la automática: actualizar P/I
            s._set_text_cell(s.tbl_cargas, row_l2, 1, DESC_LMOM_AUTO, editable=False)
            s._set_text_cell(s.tbl_cargas, row_l2, 2, f"{p_mom:.2f}", editable=False)
            s._set_text_cell(s.tbl_cargas, row_l2, 3, f"{i_mom:.2f}", editable=False)

            # Si el usuario no ha definido tiempos, aplicar propuesta inicial
            t4 = (s.tbl_cargas.item(row_l2, 4).text().strip() if s.tbl_cargas.item(row_l2, 4) else "")
            t5 = (s.tbl_cargas.item(row_l2, 5).text().strip() if s.tbl_cargas.item(row_l2, 5) else "")
            if (not t4 or t4 == "—") and (not t5 or t5 == "—"):
                t_aut = s._get_autonomia_min()
                if t_aut and float(t_aut) > 0:
                    t0_def = max(0.0, float(t_aut) - 1.0)
                    s._set_text_cell(s.tbl_cargas, row_l2, 4, f"{t0_def:.0f}", editable=False)
                    s._set_text_cell(s.tbl_cargas, row_l2, 5, "1", editable=False)

        s._apply_perfil_editability()
        if save_to_model:
            s._save_perfil_cargas_to_model()

    def run_battery_sizing(self, proyecto: dict) -> object:
        """Compute sizing, update project and mark DataModel dirty if needed."""
        res, changed = compute_and_update_project(proyecto)
        if changed and hasattr(self.screen.data_model, "mark_dirty"):
            self.screen.data_model.mark_dirty(True)
        return res
