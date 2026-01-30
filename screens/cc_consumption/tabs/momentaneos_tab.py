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


class MomentaneosTabMixin:
    def _on_mom_resumen_item_changed(self, item: QTableWidgetItem):
        if self._building:
            return
        if item.column() != MOMR_COL_DESC:
            return

        it_esc = self.tbl_mom_resumen.item(item.row(), MOMR_COL_ESC)
        if not it_esc:
            return

        esc = str(int(self._to_float(it_esc.text(), default=0)))
        desc = item.text()

        # Delegar en controller para mantener cc_escenarios y summary en sync
        self._controller.set_scenario_desc(int(esc), desc)

    def _ensure_cc_escenarios(self, n_esc: int) -> dict:
        """Asegura estructura proyecto['cc_escenarios'] en formato dict {"1": "..."}.

        - Si viene legacy list => convierte a dict y lo deja persistido.
        - Completa claves faltantes hasta n_esc con defaults.
        """
        proj = getattr(self.data_model, "proyecto", {}) or {}
        raw = proj.get("cc_escenarios")

        # Legacy: list -> dict
        if isinstance(raw, list):
            d = {}
            for i, it in enumerate(raw, start=1):
                if isinstance(it, dict):
                    desc = str(it.get("desc", "") or "").strip()
                else:
                    desc = str(it or "").strip()
                if not desc:
                    desc = f"Escenario {i}"
                d[str(i)] = desc
            raw = d
            proj["cc_escenarios"] = raw
            if hasattr(self.data_model, "mark_dirty"):
                self.data_model.mark_dirty(True)

        if not isinstance(raw, dict):
            raw = {}
            proj["cc_escenarios"] = raw
            if hasattr(self.data_model, "mark_dirty"):
                self.data_model.mark_dirty(True)

        try:
            n = int(n_esc)
        except Exception:
            n = 1
        if n < 1:
            n = 1

        for i in range(1, n + 1):
            k = str(i)
            v = str(raw.get(k, "") or "").strip()
            if not v:
                raw[k] = f"Escenario {i}"

        return raw


    def _on_mom_item_changed(self, item: QTableWidgetItem):
        """Captura cambios en checkbox 'Incluir' (y otros items) en tabla Momentáneos."""
        if self._building:
            return
        if item is None:
            return
        # Solo nos interesa el checkbox incluir
        if item.column() == MOM_COL_INCLUIR:
            self._on_mom_controls_changed(item.row())

    def _on_mom_controls_changed(self, row: int, *args):
        """Se dispara al cambiar checkbox o escenario en una fila."""
        if self._building:
            return

        it_tag = self.tbl_mom.item(row, MOM_COL_TAG)
        if not it_tag:
            return

        comp_id = str(it_tag.data(Qt.UserRole) or "").strip()
        if not comp_id:
            return

        it_inc = self.tbl_mom.item(row, MOM_COL_INCLUIR)
        incluir = bool(it_inc.checkState() == Qt.Checked) if it_inc else True

        combo = self.tbl_mom.cellWidget(row, MOM_COL_ESC)
        esc = combo.currentData() if isinstance(combo, QComboBox) else 1
        esc = int(esc) if esc else 1

        # ✅ Guardar SOLO aquí (por fila)
        self._persist_mom_flags(comp_id, incluir, esc)

        # ✅ Luego solo recalcular tabla resumen
        self._update_momentary_summary_display()

    def _update_momentary_summary_display(self):
        """
        Dominio-driven:
        - NO suma desde la tabla (widgets).
        - Lee el modelo real (instalaciones/proyecto) y pinta el resumen.
        """
        # Aseguramos que cualquier edición pendiente se materialice
        self._commit_table_edits()

        proj = getattr(self.data_model, "proyecto", {}) or {}
        gabinetes = get_model_gabinetes(self.data_model)

        vmin = getattr(self, "_vcc_for_currents", None) or get_vcc_for_currents(proj)
        n_esc = int(self.spin_escenarios.value() or 1)

        # Asegurar que flags de tabla estén persistidos antes de calcular
        for r in range(self.tbl_mom.rowCount()):
            it_tag = self.tbl_mom.item(r, MOM_COL_TAG)
            comp_id = str(it_tag.data(Qt.UserRole) or "").strip() if it_tag else ""
            if not comp_id:
                continue
            it_inc = self.tbl_mom.item(r, MOM_COL_INCLUIR)
            incluir = bool(it_inc.checkState() == Qt.Checked) if it_inc else True
            combo = self.tbl_mom.cellWidget(r, MOM_COL_ESC)
            esc = combo.currentData() if isinstance(combo, QComboBox) else 1
            esc = int(esc) if esc else 1
            self._persist_mom_flags(comp_id, incluir, esc)

        result = self._controller.compute_momentary(vmin=vmin)
        if isinstance(result, dict):
            scenarios = result.get("scenarios", {}) or {}
        else:
            scenarios = {}

        # Fallback si el controller no trae escenarios (o viene vacío)
        if not scenarios:
            scenarios = compute_momentary_scenarios_full(proj, gabinetes, vmin, n_esc) or {}

        # Normalizar claves a int (por si vienen como "1")
        scenarios_int = {}
        for k, v in (scenarios or {}).items():
            try:
                scenarios_int[int(k)] = v
            except Exception:
                continue
        scenarios = scenarios_int

        # actualizar tabla resumen
        for r in range(self.tbl_mom_resumen.rowCount()):
            it_esc = self.tbl_mom_resumen.item(r, MOMR_COL_ESC)
            if not it_esc:
                continue

            esc = int(self._to_float(it_esc.text(), default=0))
            d = scenarios.get(esc, {"p_total": 0.0, "i_total": 0.0})

            it_p = self.tbl_mom_resumen.item(r, MOMR_COL_PT)
            it_i = self.tbl_mom_resumen.item(r, MOMR_COL_IT)

            if it_p:
                it_p.setText(f"{float(d.get('p_total', 0.0)):.2f}")
            if it_i:
                it_i.setText(f"{float(d.get('i_total', 0.0)):.2f}")

        # guardar resumen en proyecto (igual que antes, pero dominio-driven)
        new_summary = {}
        for k in range(1, n_esc + 1):
            d = scenarios.get(k, {}) or {}
            new_summary[str(k)] = {
                "p_total": float(d.get("p_total", 0.0) or 0.0),
                "i_total": float(d.get("i_total", 0.0) or 0.0),
            }

        old_summary = proj.get("cc_scenarios_summary")
        if old_summary != new_summary:
            proj["cc_scenarios_summary"] = new_summary
            if hasattr(self.data_model, "mark_dirty"):
                self.data_model.mark_dirty(True)

    def _persist_scenario_descs_from_table(self):
        """UI -> modelo: guarda descripciones de escenarios en proyecto['cc_escenarios'] (dict).

        Se ejecuta en commits/reloads para no depender solo de itemChanged (pérdida de foco).
        """
        proj = getattr(self.data_model, "proyecto", {}) or {}
        n_esc = int(self.spin_escenarios.value() or 1)

        esc_names = self._ensure_cc_escenarios(n_esc)

        changed = False
        for row in range(self.tbl_mom_resumen.rowCount()):
            it_esc = self.tbl_mom_resumen.item(row, MOMR_COL_ESC)
            it_desc = self.tbl_mom_resumen.item(row, MOMR_COL_DESC)
            if not it_esc or not it_desc:
                continue

            esc = int(self._to_float(it_esc.text(), default=0))
            if esc < 1 or esc > n_esc:
                continue

            desc = (it_desc.text() or "").strip()
            if not desc:
                desc = f"Escenario {esc}"

            k = str(esc)
            if str(esc_names.get(k, "") or "") != desc:
                esc_names[k] = desc
                changed = True

            # Fuente de verdad: controller/facade (mantiene consistencia global)
            try:
                self._controller.set_scenario_desc(esc, desc)
            except Exception:
                pass

        if changed:
            proj["cc_escenarios"] = esc_names
            if hasattr(self.data_model, "mark_dirty"):
                self.data_model.mark_dirty(True)


    def _persist_mom_flags(self, comp_id: str, incluir: bool, escenario: int):
        """Persistir flags de momentáneos asociados al componente (en su bloque data)."""
        if not comp_id:
            return

        c = self._find_comp_by_id(comp_id)
        if not isinstance(c, dict):
            return

        data = c.setdefault("data", {})

        old_incluir = bool(data.get("cc_mom_incluir", True))
        old_esc = int(data.get("cc_mom_escenario", 1) or 1)

        new_incluir = bool(incluir)
        new_esc = int(escenario)
        if new_esc < 1:
            new_esc = 1

        changed = (old_incluir != new_incluir) or (old_esc != new_esc)

        data["cc_mom_incluir"] = new_incluir
        data["cc_mom_escenario"] = new_esc

        if changed and hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)

    def _load_momentaneos(self, items):
        """
        UI-only table fill. Scenario logic remains in this screen/controller.
        """
        self._building = True
        try:
            n_esc = self.spin_escenarios.value()
            load_momentaneos(self.tbl_mom, items, n_escenarios=n_esc)
        finally:
            self._building = False

        self._wire_momentary_row_controls()

        self._auto_resize(self.tbl_mom, {
            MOM_COL_GAB: 150,
            MOM_COL_TAG: 120,
            MOM_COL_DESC: 240,
            MOM_COL_PEFF: 110,
            MOM_COL_I: 110,
            MOM_COL_INCLUIR: 85,
            MOM_COL_ESC: 90,
        })


    def _wire_momentary_row_controls(self):
        """Conecta señales de controles por fila en tabla Momentáneos.

        - Checkbox (item checkable) => itemChanged (ya conectado a nivel tabla)
        - Combo de escenario (QComboBox) => currentIndexChanged por fila
        """
        for r in range(self.tbl_mom.rowCount()):
            combo = self.tbl_mom.cellWidget(r, MOM_COL_ESC)
            if isinstance(combo, QComboBox) and not bool(combo.property("_wired")):
                combo.setProperty("_wired", True)
                combo.currentIndexChanged.connect(lambda _idx, row=r: self._on_mom_controls_changed(row))

    def _rebuild_momentary_scenarios(self):
        if self._building:
            return

        self._building = True
        try:
            # Guardamos descripciones existentes (tabla) para no perder texto
            desc_prev = {}
            for row in range(self.tbl_mom_resumen.rowCount()):
                it_esc = self.tbl_mom_resumen.item(row, MOMR_COL_ESC)
                it_desc = self.tbl_mom_resumen.item(row, MOMR_COL_DESC)
                if it_esc and it_desc:
                    esc = int(self._to_float(it_esc.text(), default=0))
                    desc_prev[esc] = it_desc.text()

            proj = getattr(self.data_model, "proyecto", {}) or {}
            esc_model = get_escenarios_desc(proj)
            n_esc = self.spin_escenarios.value()

            esc_names = self._ensure_cc_escenarios(n_esc)

            # A) actualizar combos en tbl_mom sin tocar "incluir"
            for r in range(self.tbl_mom.rowCount()):
                combo = self.tbl_mom.cellWidget(r, MOM_COL_ESC)
                if not isinstance(combo, QComboBox):
                    continue

                current = combo.currentData()
                current = int(current) if current else 1

                combo.blockSignals(True)
                combo.clear()
                for n in range(1, n_esc + 1):
                    combo.addItem(str(n), n)
                if not (1 <= current <= n_esc):
                    current = 1
                idx = combo.findData(current)
                combo.setCurrentIndex(0 if idx < 0 else idx)
                combo.blockSignals(False)

                # ✅ leer el valor FINAL real del combo ya reconstruido
                final_esc = combo.currentData()
                final_esc = int(final_esc) if final_esc else 1

                it_tag = self.tbl_mom.item(r, MOM_COL_TAG)
                comp_id = str(it_tag.data(Qt.UserRole) or "").strip() if it_tag else ""
                if comp_id:
                    it_inc = self.tbl_mom.item(r, MOM_COL_INCLUIR)
                    incluir = bool(it_inc.checkState() == Qt.Checked) if it_inc else True
                    self._persist_mom_flags(comp_id, incluir, final_esc)

            # B) reconstruir tabla resumen de escenarios
            self.tbl_mom_resumen.blockSignals(True)
            self.tbl_mom_resumen.setRowCount(0)
            for n in range(1, n_esc + 1):
                row = self.tbl_mom_resumen.rowCount()
                self.tbl_mom_resumen.insertRow(row)

                it_esc = QTableWidgetItem(str(n))
                it_esc.setFlags(it_esc.flags() & ~Qt.ItemIsEditable)
                self.tbl_mom_resumen.setItem(row, MOMR_COL_ESC, it_esc)

                # Fuente de verdad: proyecto['cc_escenarios'] (dict)
                desc_db = str(esc_names.get(str(n), "") or "").strip()

                desc = desc_prev.get(n) or desc_db or f"Escenario {n}"
                it_desc = QTableWidgetItem(desc)

                self.tbl_mom_resumen.setItem(row, MOMR_COL_DESC, it_desc)

                it_p = QTableWidgetItem("0.00")
                it_p.setFlags(it_p.flags() & ~Qt.ItemIsEditable)
                self.tbl_mom_resumen.setItem(row, MOMR_COL_PT, it_p)

                it_i = QTableWidgetItem("0.00")
                it_i.setFlags(it_i.flags() & ~Qt.ItemIsEditable)
                self.tbl_mom_resumen.setItem(row, MOMR_COL_IT, it_i)

            self.tbl_mom_resumen.blockSignals(False)

            # guardar número de escenarios en proyecto
            self._set_project_value("cc_num_escenarios", int(n_esc))

            self._auto_resize(self.tbl_mom_resumen, {
                MOMR_COL_ESC: 70,
                MOMR_COL_DESC: 220,
                MOMR_COL_PT: 120,
                MOMR_COL_IT: 120,
            })

        finally:
            self._building = False

        self._update_momentary_summary_display()

    # =========================================================
    # Aleatorios
    # =========================================================
