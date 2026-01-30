# -*- coding: utf-8 -*-
"""CC Consumption tabs (mixins)

Estos mixins contienen la lógica por pestaña para evitar un cc_consumption_screen.py monolítico.
No construyen el QTabWidget; operan sobre 'self' (CCConsumptionScreen), que provee widgets y atributos.

Regla: la fuente de verdad de escenarios es proyecto['cc_escenarios'] como dict {"1": "..."}.
"""

import logging
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableWidgetItem, QComboBox

from screens.cc_consumption.widgets import (
    PERM_COL_GAB, PERM_COL_TAG, PERM_COL_DESC, PERM_COL_PW, PERM_COL_PCT, PERM_COL_P_PERM, PERM_COL_I, PERM_COL_P_MOM, PERM_COL_I_OUT,
    MOM_COL_GAB, MOM_COL_TAG, MOM_COL_DESC, MOM_COL_PEFF, MOM_COL_I, MOM_COL_INCLUIR, MOM_COL_ESC,
    MOMR_COL_ESC, MOMR_COL_DESC, MOMR_COL_PT, MOMR_COL_IT,
    ALE_COL_SEL, ALE_COL_GAB, ALE_COL_TAG, ALE_COL_DESC, ALE_COL_PEFF, ALE_COL_I,
)

log = logging.getLogger(__name__)


class AleatoriosTabMixin:
    def _load_aleatorios(self, items):
        """
        UI-only table fill.
        """
        load_aleatorios(self.tbl_ale, items)

        self._auto_resize(self.tbl_ale, {
            ALE_COL_SEL: 50,
            ALE_COL_GAB: 160,
            ALE_COL_TAG: 120,
            ALE_COL_DESC: 260,
            ALE_COL_PEFF: 110,
            ALE_COL_I: 110,
        })

    def _update_aleatory_totals(self, *args, **kwargs):
        """
        Dominio-driven:
        - 1) sincroniza selección desde la UI al modelo (cc_aleatorio_sel por ID)
        - 2) calcula totales desde el dominio leyendo el modelo real
        """
        changed = False

        # 1) UI -> modelo (persistencia robusta por ID)
        for row in range(self.tbl_ale.rowCount()):
            chk = self.tbl_ale.cellWidget(row, ALE_COL_SEL)
            selected = bool(chk.isChecked()) if chk else False

            it_tag = self.tbl_ale.item(row, ALE_COL_TAG)
            comp_id = str(it_tag.data(Qt.UserRole) or "").strip() if it_tag else ""
            if not comp_id:
                continue

            comp = self._find_comp_by_id(comp_id)
            if not isinstance(comp, dict):
                continue

            data = comp.setdefault("data", {})
            if data.get("cc_aleatorio_sel") != selected:
                data["cc_aleatorio_sel"] = selected
                changed = True

        if changed and hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)

        # 2) Modelo -> totales (dominio)
        gabinetes = get_model_gabinetes(self.data_model)
        proj = getattr(self.data_model, "proyecto", {}) or {}
        vmin = getattr(self, "_vcc_for_currents", None) or get_vcc_for_currents(proj)

        totals = compute_cc_aleatorios_totals(gabinetes, vmin)

        self.lbl_ale_total_p.setText(f"Total P aleatoria seleccionada: {totals['p_sel']:.2f} [W]")
        self.lbl_ale_total_i.setText(f"Total I aleatoria seleccionada: {totals['i_sel']:.2f} [A]")

    # =========================================================
    # Guardar imagen de tablas (tabla completa)
    # =========================================================
