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


class PermanentesTabMixin:
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

        #if self.chk_usar_global.isChecked():
        #    # En modo global sí se pisa la columna %
        #    self._apply_global_pct_mode()
        #else:
            # Solo recalculamos con los % actuales de cada fila
        #    for row in range(self.tbl_perm.rowCount()):
        #        self._update_permanent_row_i_out(row)
        #    self._update_permanent_totals()

    # ---------------- auto-refresh helpers ----------------
    def _iter_model_gabinetes(self):
        inst = getattr(self.data_model, "instalaciones", {}) or {}
        return inst.get("gabinetes", []) or []


    def _set_perm_pct_in_model(self, comp_id: str, pct_text: str):
        if not comp_id:
            return

        for gab in self._iter_model_gabinetes():  # <-- usa instalaciones
            for c in gab.get("components", []) or []:
                if c.get("id") == comp_id:
                    data = c.setdefault("data", {})
                    data["cc_perm_pct_custom"] = str(pct_text)
                    return

    # =========================================================
    # API pública
    # =========================================================


    def _load_permanentes(self, items, proyecto: dict):
        """
        UI-only table fill. Business rules live in domain/services.
        """
        usar_global = self.chk_usar_global.isChecked()
        pct_global = self.spin_pct_global.value()

        def _get_custom_pct(comp_data: dict) -> float:
            # Delegamos a helper existente (dominio)
            return float(get_pct_for_permanent(proyecto, comp_data))

        load_permanentes(
            self.tbl_perm,
            items,
            usar_global=usar_global,
            pct_global=pct_global,
            get_custom_pct=_get_custom_pct,
            update_row_cb=self._update_permanent_row_i_out,
        )

        # Solo actualizamos editabilidad (sin tocar valores)
        self._refresh_pct_editability()

        self._auto_resize(self.tbl_perm, {
            PERM_COL_GAB: 150,
            PERM_COL_TAG: 120,
            PERM_COL_DESC: 200,
            PERM_COL_PW: 90,
            PERM_COL_PCT: 110,
            PERM_COL_P_PERM: 110,
            PERM_COL_P_MOM: 110,
            PERM_COL_I: 110,
            PERM_COL_I_OUT: 110,
        })

    def _refresh_pct_editability(self):
        """
        Actualiza solo la editabilidad de la columna % Utilización
        según el estado del checkbox, sin cambiar los valores.
        """
        use_global = self.chk_usar_global.isChecked()
        for row in range(self.tbl_perm.rowCount()):
            item_pct = self.tbl_perm.item(row, PERM_COL_PCT)
            if not item_pct:
                continue
            flags = item_pct.flags()
            if use_global:
                item_pct.setFlags(flags & ~Qt.ItemIsEditable)
            else:
                item_pct.setFlags(flags | Qt.ItemIsEditable)

    def _apply_global_pct_mode(self):
        use_global = self.chk_usar_global.isChecked()
        pct_global = self.spin_pct_global.value()

        if not use_global:
            self._refresh_pct_editability()
            return

        # ✅ IMPORTANTE: mientras aplicamos el % global, NO queremos disparar itemChanged
        self._building = True
        self.tbl_perm.blockSignals(True)
        try:
            for row in range(self.tbl_perm.rowCount()):
                item_pct = self.tbl_perm.item(row, PERM_COL_PCT)
                if not item_pct:
                    continue

                item_pct.setText(f"{pct_global:.2f}")

                flags = item_pct.flags()
                item_pct.setFlags(flags & ~Qt.ItemIsEditable)

                self._update_permanent_row_i_out(row)
        finally:
            self.tbl_perm.blockSignals(False)
            self._building = False

        self._update_permanent_totals()

    def _update_permanent_row_i_out(self, row):
        """
        Recalcula P permanente, P momentánea, I permanente e I fuera %
        a partir de P total y % de utilización.
        """
        it_p_total = self.tbl_perm.item(row, PERM_COL_PW)
        it_p_perm  = self.tbl_perm.item(row, PERM_COL_P_PERM)      # P permanente [W]
        it_pct = self.tbl_perm.item(row, PERM_COL_PCT)
        if not it_p_total or not it_p_perm or not it_pct:
            return

        p_total = self._to_float(it_p_total.text(), default=0.0)

        pct = self._to_float(it_pct.text(), default=self.spin_pct_global.value())
        pct = max(0.0, min(100.0, pct))

        p_perm = p_total * (pct / 100.0)
        p_mom = max(0.0, p_total * ((100-pct) / 100.0))

        proj = getattr(self.data_model, "proyecto", {}) or {}
        vcc = getattr(self, "_vcc_for_currents", None) or get_vcc_for_currents(proj) or get_vcc_nominal(proj)

        if vcc > 0:
            i_perm = p_perm / vcc
            i_out = p_mom / vcc
        else:
            i_perm = 0.0
            i_out = 0.0

    # aseguramos items y los bloqueamos para que no sean editables
        def _ensure(col):
            item = self.tbl_perm.item(row, col)
            if item is None:
                item = QTableWidgetItem("0.00")
                self.tbl_perm.setItem(row, col, item)
            flags = item.flags()
            item.setFlags(flags & ~Qt.ItemIsEditable)
            return item

        it_p_perm = _ensure(PERM_COL_P_PERM)
        it_p_mom = _ensure(PERM_COL_P_MOM)
        it_i = _ensure(PERM_COL_I)
        it_out = _ensure(PERM_COL_I_OUT)

        it_p_perm.setText(f"{p_perm:.2f}")
        it_p_mom.setText(f"{p_mom:.2f}")

        it_i.setText(f"{i_perm:.2f}")
        it_i.setData(Qt.UserRole, float(i_perm))

        it_out.setText(f"{i_out:.2f}")
        it_out.setData(Qt.UserRole, float(i_out))

    def _update_permanent_totals(self):
        # Forzamos commit real del editor (si el usuario estaba escribiendo %)
        self._commit_table_edits()

        # --- (A) Por seguridad: si NO usas global, sincroniza % desde tabla a modelo
        #     Esto cubre casos donde itemChanged no alcanzó a disparar por focus raro.
        changed = False
        if not self.chk_usar_global.isChecked():
            for row in range(self.tbl_perm.rowCount()):
                it_tag = self.tbl_perm.item(row, PERM_COL_TAG)
                it_pct = self.tbl_perm.item(row, PERM_COL_PCT)
                if not it_tag or not it_pct:
                    continue

                comp_id = str(it_tag.data(Qt.UserRole) or "").strip()
                if not comp_id:
                    continue

                comp = self._find_comp_by_id(comp_id)
                if not isinstance(comp, dict):
                    continue

                raw = (it_pct.text() or "").strip()
                pct = self._to_float(raw, default=self.spin_pct_global.value())
                pct = max(0.0, min(100.0, pct))
                new_val = f"{pct:.2f}"

                data = comp.setdefault("data", {})
                if data.get("cc_perm_pct_custom") != new_val:
                    data["cc_perm_pct_custom"] = new_val
                    changed = True

        if changed and hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)

        # --- (B) Totales dominio-driven ---
        proj = getattr(self.data_model, "proyecto", {}) or {}
        vmin = getattr(self, "_vcc_for_currents", None) or get_vcc_for_currents(proj)
        totals = self._controller.compute_totals(vmin=float(vmin))

        self.lbl_perm_total_p_total.setText(f"Total P total: {totals.get('p_total', totals.get('p_perm', 0.0) + totals.get('p_mom', 0.0)):.2f} [W]")
        self.lbl_perm_total_p_perm.setText(f"Total P permanente: {totals['p_perm']:.2f} [W]")
        self.lbl_perm_total_i.setText(f"Total I permanente: {totals['i_perm']:.2f} [A]")
        self.lbl_perm_total_p_mom.setText(f"Total P momentánea: {totals['p_mom']:.2f} [W]")
        self.lbl_perm_total_i_fuera.setText(f"Total I momentánea: {totals['i_mom']:.2f} [A]")
        # (totales momentáneos ocultos en UI)

    def _on_global_pct_changed(self, value):
        if self._building:
            return

        # 1) Guardar SIEMPRE en el proyecto (como referencia)
        self._controller.set_pct_global(float(value))

        # 2) Avisar hacia fuera (pestaña Proyecto)
        self.porcentaje_util_changed.emit(float(value))

        # 3) SOLO si el check está activo, aplicamos el global
        if self.chk_usar_global.isChecked():
            self._apply_global_pct_mode()
        else:
            # Si el global está desactivado, no tocamos la columna de %,
            # solo recalculamos corrientes por si dependieran de algo más.
            for row in range(self.tbl_perm.rowCount()):
                self._update_permanent_row_i_out(row)
            self._update_permanent_totals()

    def _on_perm_item_changed(self, item: QTableWidgetItem):
        if self._building:
            return

        # Solo nos interesa el % por fila
        if item.column() != PERM_COL_PCT:
            return

        # Si está activo el % global, ignorar (en teoría ni debería ser editable)
        if self.chk_usar_global.isChecked():
            return

        row = item.row()
        it_tag = self.tbl_perm.item(row, PERM_COL_TAG)
        if not it_tag:
            return

        comp_id = str(it_tag.data(Qt.UserRole) or "").strip()
        if not comp_id:
            return

        comp = self._find_comp_by_id(comp_id)
        if not isinstance(comp, dict):
            return

        raw = (item.text() or "").strip()
        pct = self._to_float(raw, default=self.spin_pct_global.value())
        pct = max(0.0, min(100.0, pct))
        item.setText(f"{pct:.2f}")

        data = comp.setdefault("data", {})
        new_val = f"{pct:.2f}"

        if data.get("cc_perm_pct_custom") != new_val:
            data["cc_perm_pct_custom"] = new_val
            if hasattr(self.data_model, "mark_dirty"):
                self.data_model.mark_dirty(True)

            self._update_permanent_row_i_out(row)
            self._update_permanent_totals()

    # =========================================================
    # Momentáneos
    # =========================================================
