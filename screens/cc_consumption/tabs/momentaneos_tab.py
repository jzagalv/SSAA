# -*- coding: utf-8 -*-
"""CC Consumption tabs (mixins)

Estos mixins contienen la lógica por pestaña para evitar un cc_consumption_screen.py monolítico.
No construyen el QTabWidget; operan sobre 'self' (CCConsumptionScreen), que provee widgets y atributos.

Regla: la fuente de verdad de escenarios es proyecto['cc_escenarios'] como dict {"1": "..."}.
"""

from PyQt5.QtWidgets import QHeaderView, QAbstractItemView

from domain.cc_consumption import (
    get_vcc_for_currents,
)

from screens.cc_consumption.models.momentaneos_loads_table_model import (
    MomentaneosLoadsTableModel,
    ScenarioComboDelegate,
)
from screens.cc_consumption.models.momentaneos_scenarios_table_model import (
    MomentaneosScenariosTableModel,
    ScenarioRow,
)
from screens.cc_consumption.utils import resolve_scenario_desc
from ui.utils.table_utils import configure_table_autoresize, request_autofit
from screens.cc_consumption.table_schema import (
    MOM_COL_GAB, MOM_COL_TAG, MOM_COL_DESC, MOM_COL_PEFF, MOM_COL_I, MOM_COL_INCLUIR, MOM_COL_ESC,
    MOMR_COL_PERM, MOMR_COL_ESC, MOMR_COL_DESC, MOMR_COL_PT, MOMR_COL_IT,
)


class MomentaneosTabMixin:
    def _ensure_mom_model(self):
        if getattr(self, "_mom_model", None) is None:
            self._mom_model = MomentaneosLoadsTableModel(self._controller, parent=self)
            self.tbl_mom.setModel(self._mom_model)
            configure_table_autoresize(self.tbl_mom)
            self.tbl_mom.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.tbl_mom.setSelectionMode(QAbstractItemView.SingleSelection)
            self._mom_delegate = ScenarioComboDelegate(self.tbl_mom, min_value=1, max_value=20)
            self.tbl_mom.setItemDelegateForColumn(MOM_COL_ESC, self._mom_delegate)
            self._mom_model.dataChanged.connect(self._on_mom_loads_changed)

    def _ensure_mom_scenarios_model(self):
        if getattr(self, "_mom_scenarios_model", None) is None:
            self._mom_scenarios_model = MomentaneosScenariosTableModel(self._controller, parent=self)
            self.tbl_mom_resumen.setModel(self._mom_scenarios_model)
            configure_table_autoresize(self.tbl_mom_resumen)
            header = self.tbl_mom_resumen.horizontalHeader()
            header.setSectionResizeMode(MOMR_COL_PERM, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(MOMR_COL_DESC, QHeaderView.Stretch)
            self._mom_scenarios_model.dataChanged.connect(self._on_mom_scenarios_changed)

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
                    desc = ""
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
            if k not in raw or raw.get(k) is None:
                raw[k] = ""

        return raw

    def _ensure_cc_mom_incl_perm(self, n_esc: int) -> dict:
        """
        Asegura proyecto['cc_mom_incl_perm'] como dict {"1": bool, ...}.

        Migración legacy:
        - Si no existe cc_mom_incl_perm pero existe cc_mom_perm_target_scenario,
          crea mapa con todo False y sólo ese escenario en True.
        """
        proj = getattr(self.data_model, "proyecto", {}) or {}
        changed = False
        include_map = proj.get("cc_mom_incl_perm")
        had_map = isinstance(include_map, dict)

        try:
            n = int(n_esc)
        except Exception:
            n = 1
        if n < 1:
            n = 1

        if not isinstance(include_map, dict):
            include_map = {}
            legacy_target = proj.get("cc_mom_perm_target_scenario", None)
            if legacy_target is not None:
                try:
                    target = int(legacy_target or 1)
                except Exception:
                    target = 1
                if target < 1 or target > n:
                    target = 1
                for i in range(1, n + 1):
                    include_map[str(i)] = (i == target)
            proj["cc_mom_incl_perm"] = include_map
            changed = True

        for i in range(1, n + 1):
            k = str(i)
            if k not in include_map:
                include_map[k] = False
                changed = True
                continue
            raw = include_map.get(k)
            if isinstance(raw, str):
                val = raw.strip().casefold() in ("1", "true", "yes", "on")
            else:
                val = bool(raw)
            if include_map.get(k) is not val:
                include_map[k] = val
                changed = True

        if changed and hasattr(self.data_model, "mark_dirty"):
            # Al migrar desde legacy, persistimos el nuevo esquema.
            self.data_model.mark_dirty(True)

        if not had_map and hasattr(self, "_autosave_project_best_effort"):
            self._autosave_project_best_effort()

        return include_map

    def _on_mom_loads_changed(self, *args):
        if self._building or getattr(self, "_loading", False):
            return
        try:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, self._update_momentary_summary_display)
        except Exception:
            self._update_momentary_summary_display()

    def _on_mom_scenarios_changed(self, top_left, bottom_right, roles=None):
        if self._building or getattr(self, "_loading", False):
            return
        if top_left.column() > MOMR_COL_PERM or bottom_right.column() < MOMR_COL_PERM:
            return
        if hasattr(self, "invalidate_calculated_cc"):
            self.invalidate_calculated_cc()
        self._update_momentary_summary_display()
        if hasattr(self, "_update_permanent_totals"):
            self._update_permanent_totals()
        if hasattr(self, "_autosave_project_best_effort"):
            self._autosave_project_best_effort()

    def _clamp_momentary_model_scenarios(self, n_esc: int) -> None:
        model = getattr(self, "_mom_model", None)
        if model is None:
            return
        for r in range(model.rowCount()):
            row = model.get_row(r)
            if row is None:
                continue
            esc = int(row.escenario or 1)
            if not (1 <= esc <= n_esc):
                esc = 1
                model.set_row_escenario(r, esc)
            if row.comp_id:
                self._persist_mom_flags(row.comp_id, bool(row.incluir), esc)

    def _update_momentary_summary_display(self):
        """
        Render de resumen por escenario usando estado actual del modelo
        y bandera por escenario `cc_mom_incl_perm`.
        """
        if getattr(self, "_loading", False):
            return
        # Aseguramos que cualquier edición pendiente se materialice.
        self._commit_table_edits()

        proj = getattr(self.data_model, "proyecto", {}) or {}
        n_esc = int(self.spin_escenarios.value() or 1)
        self._ensure_cc_escenarios(n_esc)
        include_map = self._ensure_cc_mom_incl_perm(n_esc)

        by_scenario = {}
        cc_results = proj.get("cc_results", None)
        if isinstance(cc_results, dict):
            raw_by_scenario = cc_results.get("by_scenario", None)
            if isinstance(raw_by_scenario, dict) and raw_by_scenario:
                by_scenario = raw_by_scenario
        if not by_scenario:
            vmin = getattr(self, "_vcc_for_currents", None) or get_vcc_for_currents(proj) or 1.0
            try:
                vmin = float(vmin or 0.0)
            except Exception:
                vmin = 1.0
            if vmin <= 0.0:
                vmin = 1.0
            try:
                by_scenario = self._controller.compute_momentary(vmin=float(vmin)) or {}
            except Exception:
                by_scenario = {}

        def _scenario_totals(idx: int) -> tuple[float, float]:
            raw = by_scenario.get(str(idx), by_scenario.get(idx, {}))
            if not isinstance(raw, dict):
                return 0.0, 0.0
            try:
                p_total = float(raw.get("p_total", 0.0) or 0.0)
            except Exception:
                p_total = 0.0
            try:
                i_total = float(raw.get("i_total", 0.0) or 0.0)
            except Exception:
                i_total = 0.0
            return p_total, i_total

        # actualizar tabla resumen
        self._ensure_mom_scenarios_model()
        rows = []
        for n in range(1, n_esc + 1):
            desc_db = ""
            try:
                desc_db = self._controller.get_scenario_desc(n)
            except Exception:
                desc_db = ""
            desc = resolve_scenario_desc(n, "", desc_db)
            p_total, i_total = _scenario_totals(n)
            rows.append(
                ScenarioRow(
                    n=int(n),
                    include_perm=bool(include_map.get(str(n), False)),
                    desc=desc,
                    p_total=p_total,
                    i_total=i_total,
                )
            )
        if getattr(self, "_mom_scenarios_model", None) is not None:
            self._mom_scenarios_model.set_rows(rows)

    def _persist_mom_flags(self, comp_id: str, incluir: bool, escenario: int):
        """Persistir flags de momentáneos asociados al componente (en su bloque data)."""
        if not comp_id:
            return
        self._controller.set_momentary_flags(comp_id, incluir, escenario)

    def _load_momentaneos(self, items):
        """
        UI-only table fill. Scenario logic remains in this screen/controller.
        """
        self._building = True
        self._loading = True
        try:
            n_esc = self.spin_escenarios.value()
            self._ensure_mom_model()
            if getattr(self, "_mom_delegate", None) is not None:
                self._mom_delegate.set_range(1, int(n_esc))
            self._mom_model.set_items(items)
            self._clamp_momentary_model_scenarios(int(n_esc))
        finally:
            self._loading = False
            self._building = False

        request_autofit(self.tbl_mom)
        try:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, self._update_momentary_summary_display)
        except Exception:
            self._update_momentary_summary_display()

    def _rebuild_momentary_scenarios(self):
        if self._building:
            return

        self._building = True
        try:
            n_esc = self.spin_escenarios.value()
            self._ensure_cc_escenarios(n_esc)
            if getattr(self, "_mom_delegate", None) is not None:
                self._mom_delegate.set_range(1, int(n_esc))

            # A) ajustar escenarios en model (clamp) sin tocar "incluir"
            self._clamp_momentary_model_scenarios(int(n_esc))

            # Guardar numero de escenarios en proyecto
            self._set_project_value("cc_num_escenarios", int(n_esc))

            # Ensure summary model exists and size columns
            self._ensure_mom_scenarios_model()
            request_autofit(self.tbl_mom_resumen)
        finally:
            self._building = False

        self._update_momentary_summary_display()

    # =========================================================
    # Aleatorios
    # =========================================================
