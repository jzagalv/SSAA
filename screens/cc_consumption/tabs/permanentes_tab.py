# -*- coding: utf-8 -*-
"""CC Consumption tabs (mixins)

Estos mixins contienen la lógica por pestaña para evitar un cc_consumption_screen.py monolítico.
No construyen el QTabWidget; operan sobre 'self' (CCConsumptionScreen), que provee widgets y atributos.

Regla: la fuente de verdad de escenarios es proyecto['cc_escenarios'] como dict {"1": "..."}.
"""

from PyQt5.QtWidgets import QHeaderView, QAbstractItemView

from domain.cc_consumption import get_pct_for_permanent, get_vcc_for_currents, get_vcc_nominal

from screens.cc_consumption.widgets import (
    PERM_COL_GAB, PERM_COL_TAG, PERM_COL_DESC, PERM_COL_PW, PERM_COL_PCT, PERM_COL_P_PERM, PERM_COL_I, PERM_COL_P_MOM, PERM_COL_I_OUT,
)
from screens.cc_consumption.models.permanentes_table_model import PermanentesTableModel
from ui.utils.table_utils import configure_table_autoresize, request_autofit

class PermanentesTabMixin:
    def _ensure_perm_model(self):
        if getattr(self, "_perm_model", None) is None:
            self._perm_model = PermanentesTableModel(parent=self)
            self.tbl_perm.setModel(self._perm_model)
            configure_table_autoresize(self.tbl_perm)
            self.tbl_perm.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.tbl_perm.setSelectionMode(QAbstractItemView.SingleSelection)
            self._perm_model.dataChanged.connect(self._on_perm_data_changed)

    def set_pct_from_outside(self, pct: float):
        """
        Llamado desde la pestaña Proyecto cuando cambia el % de utilización.
        - Actualiza el spin local.
        - Si 'Usar % global' está ACTIVADO, aplica el % a todas las filas.
        - Si 'Usar % global' está DESACTIVADO, NO toca los % de la tabla;
          solo recalcula corrientes y totales con los % ya existentes.
        """
        try:
            self._building = True
            self.spin_pct_global.setValue(float(pct))
        finally:
            self._building = False

    # =========================================================
    # API pública
    # =========================================================


    def _load_permanentes(self, items, proyecto: dict):
        """
        UI-only table fill. Business rules live in domain/services.
        """
        usar_global = self.chk_usar_global.isChecked()
        pct_global = self.spin_pct_global.value()
        vmin = getattr(self, "_vcc_for_currents", None) or get_vcc_for_currents(proyecto) or get_vcc_nominal(proyecto)

        def _get_custom_pct(comp_data: dict) -> float:
            # Delegamos a helper existente (dominio)
            return float(get_pct_for_permanent(proyecto, comp_data))

        self._ensure_perm_model()
        self._perm_model.set_items(
            items,
            use_global=usar_global,
            pct_global=pct_global,
            get_custom_pct=_get_custom_pct,
            vmin=float(vmin or 0.0),
        )

        # Solo actualizamos editabilidad (sin tocar valores)
        self._refresh_pct_editability()

        request_autofit(self.tbl_perm)

    def _refresh_pct_editability(self):
        """
        Actualiza solo la editabilidad de la columna % Utilización
        según el estado del checkbox, sin cambiar los valores.
        """
        use_global = self.chk_usar_global.isChecked()
        if getattr(self, "_perm_model", None) is not None:
            self._perm_model.set_use_global(use_global)
            try:
                self._perm_model.layoutChanged.emit()
            except Exception:
                pass

    def _apply_global_pct_mode(self):
        use_global = self.chk_usar_global.isChecked()
        pct_global = self.spin_pct_global.value()

        if not use_global:
            self._refresh_pct_editability()
            return

        vmin = getattr(self, "_vcc_for_currents", None) or get_vcc_for_currents(getattr(self.data_model, "proyecto", {}) or {}) or 0.0
        if getattr(self, "_perm_model", None) is not None:
            self._perm_model.apply_global_pct(float(pct_global), float(vmin))

        try:
            self._controller._emit_input_changed({"perm_pct": True})
        except Exception:
            pass

    def _update_permanent_totals(self):
        proj = getattr(self.data_model, "proyecto", {}) or {}
        vmin = getattr(self, "_vcc_for_currents", None) or get_vcc_for_currents(proj) or 1.0
        totals = self._controller.compute_totals(vmin=float(vmin))

        p_total = float(totals.get("p_total", 0.0) or 0.0)
        p_perm = float(totals.get("p_perm", 0.0) or 0.0)
        i_perm = float(totals.get("i_perm", 0.0) or 0.0)
        p_mom = float(totals.get("p_mom", 0.0) or 0.0)
        i_mom = float(totals.get("i_mom", 0.0) or 0.0)

        self.lbl_perm_total_p_total.setText(f"Total P total: {p_total:.2f} [W]")
        self.lbl_perm_total_p_perm.setText(f"Total P permanente: {p_perm:.2f} [W]")
        self.lbl_perm_total_i.setText(f"Total I permanente: {i_perm:.2f} [A]")
        self.lbl_perm_total_p_mom.setText(f"Total P moment?nea: {p_mom:.2f} [W]")
        self.lbl_perm_total_i_fuera.setText(f"Total I moment?nea: {i_mom:.2f} [A]")

    def _on_perm_data_changed(self, top_left, bottom_right, roles=None):
        if self._building:
            return
        if self.chk_usar_global.isChecked():
            return
        model = getattr(self, "_perm_model", None)
        if model is None:
            return
        for row in range(top_left.row(), bottom_right.row() + 1):
            r = model.get_row(row)
            if r is None or not r.comp_id:
                continue
            comp = self._find_comp_by_id(r.comp_id)
            if not isinstance(comp, dict):
                continue
            pct = max(0.0, min(100.0, float(r.pct)))
            new_val = f"{pct:.2f}"
            data = comp.setdefault("data", {})
            if data.get("cc_perm_pct_custom") != new_val:
                data["cc_perm_pct_custom"] = new_val
                if hasattr(self.data_model, "mark_dirty"):
                    self.data_model.mark_dirty(True)
        try:
            self._controller._emit_input_changed({"perm_pct": True})
        except Exception:
            pass

    # =========================================================
    # Momentaneos
