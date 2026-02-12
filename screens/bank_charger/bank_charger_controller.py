# -*- coding: utf-8 -*-
"""Bank Charger controller.

Extracted from bank_charger_screen.py to reduce file size and improve separation.
Low-risk approach: controller holds a reference to the screen and operates on its widgets.
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any

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



# Constants shared with bank_charger_screen
DURACION_MIN_GRAFICA_MIN = 10.0
CODE_L1 = "L1"
CODE_LAL = "L(al)"


from services.bank_charger_service import compute_and_update_project
from app.base_controller import BaseController
from core.sections import Section


class BankChargerController(BaseController):
    def __init__(self, screen):
        super().__init__(screen=screen, section=Section.BANK_CHARGER)
        self.screen = screen
        self.selection_presenter = SelectionTablesPresenter(
            screen,
            on_k1_changed=screen._on_bank_k1_changed,
            on_k2_changed=screen._on_bank_k2_changed,
            on_k3_changed=screen._on_bank_k3_changed,
        )
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

    @staticmethod
    def _stable_dump(value: Any) -> str:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)

    def save_perfil_cargas_to_model(self):
        prev_perfil = self.persistence.get_saved_perfil_cargas()
        next_perfil = self.persistence.collect_perfil_cargas()
        next_random = self.persistence.collect_random_loads(next_perfil)
        changed = self._stable_dump(prev_perfil) != self._stable_dump(next_perfil)
        synced = self.persistence.is_perfil_storage_synced(next_perfil, next_random)
        if not changed and synced:
            return False
        self.persistence.save_perfil_cargas(next_perfil, next_random)
        if changed:
            self.mark_dirty()
        return changed


    
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
        prev_store = self.persistence.get_ieee485_kt_data()
        next_store = self.persistence.collect_ieee485_kt()
        if self._stable_dump(prev_store) == self._stable_dump(next_store):
            return False
        self.persistence.save_ieee485_kt(next_store)
        self.mark_dirty()
        return True

    def save_ieee_kt_to_model(self):
        return self.persist_ieee_kt_to_model()

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


    def reset_loaded_flags(self) -> None:
        s = self.screen
        s._perfil_loaded = False
        s._ieee_loaded = False
        s._seleccion_loaded = False
        s._resumen_loaded = False

    def reload_from_project(self):
        s = self.screen
        """Recarga datos desde data_model.proyecto (incluye Perfil de cargas guardado)."""
        self.reset_loaded_flags()

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
        perfil_guardado = self.persistence.get_saved_perfil_cargas()
        random_guardado = self.persistence.get_saved_random_loads()
        has_persisted = bool(perfil_guardado) or bool(random_guardado)

        if not has_persisted:
            # New/legacy-empty projects: initialize canonical defaults and persist them.
            s._fill_perfil_cargas(save_to_model=True)
        s._load_perfil_cargas_from_model()
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
    def run_battery_sizing(self, proyecto: dict) -> object:
        """Compute sizing, update project and mark DataModel dirty if needed."""
        res, changed = compute_and_update_project(proyecto)
        if changed and hasattr(self.screen.data_model, "mark_dirty"):
            self.screen.data_model.mark_dirty(True)
        return res
