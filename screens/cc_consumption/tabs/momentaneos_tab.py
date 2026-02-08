# -*- coding: utf-8 -*-
"""CC Consumption tabs (mixins)

Estos mixins contienen la lógica por pestaña para evitar un cc_consumption_screen.py monolítico.
No construyen el QTabWidget; operan sobre 'self' (CCConsumptionScreen), que provee widgets y atributos.

Regla: la fuente de verdad de escenarios es proyecto['cc_escenarios'] como dict {"1": "..."}.
"""

from PyQt5.QtWidgets import QHeaderView, QAbstractItemView

from domain.cc_consumption import get_vcc_for_currents, momentary_state_signature

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
    MOMR_COL_ESC, MOMR_COL_DESC, MOMR_COL_PT, MOMR_COL_IT,
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

    def _on_mom_loads_changed(self, *args):
        if self._building:
            return
        self._mom_force_recalc = True
        try:
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, self._update_momentary_summary_display)
        except Exception:
            self._update_momentary_summary_display()

    def _update_momentary_summary_display(self):
        """
        Display-only: reads computed results from calculated.cc.scenarios_totals,
        with controller fallback when missing.
        """
        # Aseguramos que cualquier edición pendiente se materialice
        self._commit_table_edits()

        proj = getattr(self.data_model, "proyecto", {}) or {}
        n_esc = int(self.spin_escenarios.value() or 1)
        self._ensure_cc_escenarios(n_esc)

        by_scenario = {}
        vmin = getattr(self, "_vcc_for_currents", None) or get_vcc_for_currents(proj) or 1.0
        force = bool(getattr(self, "_mom_force_recalc", False))

        model = getattr(self, "_mom_model", None)
        rows = []
        if model is not None:
            for r in range(model.rowCount()):
                row = model.get_row(r)
                if row is None:
                    continue
                rows.append({
                    "comp_id": row.comp_id,
                    "incluir": bool(row.incluir),
                    "escenario": int(row.escenario or 1),
                    "p_efectiva_w": float(row.p_eff or 0.0),
                    "i_a": float(row.i_eff or 0.0),
                })

        sig_now = momentary_state_signature(rows, vmin=float(vmin), n_scenarios=int(n_esc))

        calc = proj.get("calculated")
        if not isinstance(calc, dict):
            calc = {}
            proj["calculated"] = calc
        cc_calc = calc.get("cc")
        if not isinstance(cc_calc, dict):
            cc_calc = {}
            calc["cc"] = cc_calc

        cached_totals = cc_calc.get("scenarios_totals")
        cached_sig = cc_calc.get("momentary_signature")
        use_cache = (
            isinstance(cached_totals, dict)
            and cached_totals
            and cached_sig == sig_now
            and not force
        )

        if use_cache:
            by_scenario = cached_totals
        else:
            computed = self._controller.compute_momentary(vmin=float(vmin))
            if isinstance(computed, dict):
                by_scenario = {}
                for k, v in (computed or {}).items():
                    try:
                        by_scenario[str(int(k))] = v
                    except Exception:
                        continue
                cc_calc["scenarios_totals"] = by_scenario
                cc_calc["momentary_signature"] = sig_now
                if hasattr(self.data_model, "mark_dirty"):
                    self.data_model.mark_dirty(True)
            self._mom_force_recalc = False

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
            d = by_scenario.get(str(n), by_scenario.get(n, {})) or {}
            rows.append(
                ScenarioRow(
                    n=int(n),
                    desc=desc,
                    p_total=float(d.get("p_total", 0.0) or 0.0),
                    i_total=float(d.get("i_total", 0.0) or 0.0),
                )
            )
        if getattr(self, "_mom_scenarios_model", None) is not None:
            self._mom_scenarios_model.set_rows(rows)

        # guardar resumen de totales en calculated.cc.scenarios_totals (no cc_scenarios_summary)
        scenarios_totals = {}
        for k in range(1, n_esc + 1):
            d = by_scenario.get(str(k), by_scenario.get(k, {})) or {}
            scenarios_totals[str(k)] = {
                "p_total": float(d.get("p_total", 0.0) or 0.0),
                "i_total": float(d.get("i_total", 0.0) or 0.0),
            }

        if cc_calc.get("scenarios_totals") != scenarios_totals:
            cc_calc["scenarios_totals"] = scenarios_totals
            if hasattr(self.data_model, "mark_dirty"):
                self.data_model.mark_dirty(True)

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
        try:
            n_esc = self.spin_escenarios.value()
            self._ensure_mom_model()
            if getattr(self, "_mom_delegate", None) is not None:
                self._mom_delegate.set_range(1, int(n_esc))
            self._mom_model.set_items(items)
        finally:
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
            model = getattr(self, "_mom_model", None)
            if model is not None:
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
