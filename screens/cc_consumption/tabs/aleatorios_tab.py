# -*- coding: utf-8 -*-
"""CC Consumption tabs (mixins)

Estos mixins contienen la lógica por pestaña para evitar un cc_consumption_screen.py monolítico.
No construyen el QTabWidget; operan sobre 'self' (CCConsumptionScreen), que provee widgets y atributos.

Regla: la fuente de verdad de escenarios es proyecto['cc_escenarios'] como dict {"1": "..."}.
"""

from PyQt5.QtWidgets import QHeaderView, QAbstractItemView

from domain.cc_consumption import get_vcc_for_currents



from screens.cc_consumption.table_schema import (
    ALE_COL_SEL, ALE_COL_GAB, ALE_COL_TAG, ALE_COL_DESC, ALE_COL_PEFF, ALE_COL_I,
)
from screens.cc_consumption.models.aleatorios_table_model import AleatoriosTableModel

class AleatoriosTabMixin:
    def _ensure_ale_model(self):
        if getattr(self, "_ale_model", None) is None:
            self._ale_model = AleatoriosTableModel(self._controller, parent=self)
            self.tbl_ale.setModel(self._ale_model)
            header = self.tbl_ale.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Interactive)
            header.setStretchLastSection(False)
            self.tbl_ale.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.tbl_ale.setSelectionMode(QAbstractItemView.SingleSelection)
            self._ale_model.dataChanged.connect(self._update_aleatory_totals)

    def _load_aleatorios(self, items):
        """
        Model-only table fill.
        """
        self._ensure_ale_model()
        self._ale_model.set_items(items)

        self._auto_resize(self.tbl_ale, {
            ALE_COL_SEL: 50,
            ALE_COL_GAB: 160,
            ALE_COL_TAG: 120,
            ALE_COL_DESC: 260,
            ALE_COL_PEFF: 110,
            ALE_COL_I: 110,
        })
        self._update_aleatory_totals()

    def _update_aleatory_totals(self, *args, **kwargs):
        """
        Dominio-driven:
        - 1) sincroniza selección desde la UI al modelo (cc_aleatorio_sel por ID)
        - 2) calcula totales desde el dominio leyendo el modelo real
        """
        try:
            self.commit_pending_edits()
        except Exception:
            pass
        # UI -> modelo now handled by the table model (setData)

        # 2) Totales desde controller
        proj = getattr(self.data_model, "proyecto", {}) or {}
        vmin = getattr(self, "_vcc_for_currents", None) or get_vcc_for_currents(proj) or 1.0
        rnd = self._controller.compute_random(vmin=float(vmin))

        p_sel = float(rnd.get("p_sel", 0.0) or 0.0)
        i_sel = float(rnd.get("i_sel", 0.0) or 0.0)

        self.lbl_ale_total_p.setText(f"Total P aleatoria seleccionada: {p_sel:.2f} [W]")
        self.lbl_ale_total_i.setText(f"Total I aleatoria seleccionada: {i_sel:.2f} [A]")

    # =========================================================
    # Guardar imagen de tablas (tabla completa)
    # =========================================================
