# -*- coding: utf-8 -*-
"""CC Consumption Controller (screens/cc_consumption)

Objetivo:
- Mantener cc_consumption_screen.py enfocado en UI (Qt) + renderizado.
- Centralizar cambios al proyecto (DataModel.proyecto) y recalculos derivados.
- Encapsular claves persistidas vía ProjectFacade/ProjectKeys (sin strings mágicos en UI).

Este controller NO depende de PyQt.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from core.sections import Section
from app.base_controller import BaseController
from domain.project_facade import ProjectFacade
from domain.cc_consumption import (
    get_model_gabinetes,
    compute_cc_permanentes_totals,
    compute_momentary_scenarios_full,
    compute_cc_aleatorios_totals,
    get_num_escenarios,
)
from services.calc_service import CalcService

log = logging.getLogger(__name__)


class CCConsumptionController(BaseController):

    def _emit_metadata_changed(self, fields: Dict[str, Any]) -> None:
        dm = self.data_model
        if dm is None:
            return
        bus = getattr(dm, "event_bus", None)
        if bus is None:
            return
        try:
            from app.events import MetadataChanged
            bus.emit(MetadataChanged(section=Section.CC, fields=fields))
        except Exception:
            log.debug("MetadataChanged emit failed (best-effort).", exc_info=True)

    def _emit_input_changed(self, fields: Dict[str, Any]) -> None:
        dm = self.data_model
        if dm is None:
            return
        bus = getattr(dm, "event_bus", None)
        if bus is None:
            return
        try:
            from app.events import InputChanged
            bus.emit(InputChanged(section=Section.CC, fields=fields))
        except Exception:
            log.debug("InputChanged emit failed (best-effort).", exc_info=True)

    def __init__(self, data_model):
        super().__init__(data_model, section=Section.CC)

    def project(self) -> Dict[str, Any]:
        proj = getattr(self.data_model, "proyecto", {}) or {}
        return proj if isinstance(proj, dict) else {}

    def facade(self) -> ProjectFacade:
        return ProjectFacade(self.project())

    # mark_dirty()/notify_changed() provided by BaseController

    # -------- specific settings (persisted at top-level) --------
    def set_project_value(self, key: str, value) -> None:
        """Set a raw project key (legacy/UI helper).

        Prefer using facade-specific setters where available, but keep this
        for UI code that still calls _set_project_value(...).
        """
        proj = self.project()
        # Avoid unnecessary dirty flips
        old = proj.get(key, None)
        if old == value:
            return
        proj[key] = value
        self.mark_dirty()

    def set_pct_global(self, pct: float) -> bool:
        fac = self.facade()
        before = fac.get_utilization_pct_global()
        fac.set_utilization_pct_global(float(pct))
        after = fac.get_utilization_pct_global()
        if after != before:
            self.mark_dirty()
            self._emit_input_changed({"pct_global": after})
            return True
        return False

    def set_use_pct_global(self, use: bool) -> bool:
        fac = self.facade()
        before = fac.get_cc_use_pct_global()
        fac.set_cc_use_pct_global(bool(use))
        after = fac.get_cc_use_pct_global()
        if after != before:
            self.mark_dirty()
            self._emit_input_changed({"use_pct_global": after})
            return True
        return False

    def set_scenario_desc(self, esc: int, desc: str, notify: bool = False) -> bool:
        """Actualiza descripción del escenario (fuente de verdad: ProjectFacade).

        Reglas:
        - Normaliza el número de escenario a >= 1
        - Normaliza el texto (strip). Si queda vacío => "Escenario N"
        - Mantiene sincronizado el summary legacy (lista de dicts) para compatibilidad.
        """
        fac = self.facade()

        esc_i = int(esc) if esc else 1
        if esc_i < 1:
            esc_i = 1
        esc_key = str(esc_i)

        desc_clean = (str(desc) if desc is not None else "").strip()

        scenarios = fac.get_cc_scenarios() or {}
        before = str(scenarios.get(esc_key, "") or "")
        if desc_clean == before:
            return False

        fac.update_cc_scenario_desc(esc_key, desc_clean)

        # ---- Compatibilidad: mantener summary legacy en sync (si existe) ----
        summary = fac.get_cc_scenarios_summary()
        if not isinstance(summary, list):
            summary = []

        updated = False
        for row in summary:
            if isinstance(row, dict) and str(row.get("escenario", "")) == esc_key:
                row["descripcion"] = desc_clean
                updated = True
                break
        if not updated:
            summary.append({"escenario": esc_key, "descripcion": desc_clean})
        fac.set_cc_scenarios_summary(summary)

        self.mark_dirty()
        if notify:
            self.notify_changed()
        self._emit_metadata_changed({"scenario_name": esc_i})
        return True

    def get_scenario_desc(self, esc: int) -> str:
        """Get scenario description from the canonical cc_escenarios dict."""
        esc_i = int(esc) if esc else 1
        if esc_i < 1:
            esc_i = 1
        fac = self.facade()
        scenarios = fac.get_cc_scenarios() or {}
        return str(scenarios.get(str(esc_i), "") or "")

    def set_scenario_enabled(self, esc: int, enabled: bool, notify: bool = False) -> bool:
        """Actualiza habilitación de escenario para cálculo de totales momentáneos."""
        fac = self.facade()

        esc_i = int(esc) if esc else 1
        if esc_i < 1:
            esc_i = 1
        esc_key = str(esc_i)

        enabled_map = fac.get_cc_scenarios_enabled() or {}
        before = bool(enabled_map.get(esc_key, True))
        after = bool(enabled)
        if before == after:
            return False

        fac.update_cc_scenario_enabled(esc_key, after)

        # Compatibilidad legacy: mantener cc_scenarios_summary sincronizado si existe.
        summary = fac.get_cc_scenarios_summary()
        if not isinstance(summary, list):
            summary = []
        updated = False
        for row in summary:
            if isinstance(row, dict) and str(row.get("escenario", "")) == esc_key:
                row["enabled"] = after
                updated = True
                break
        if not updated:
            summary.append({"escenario": esc_key, "enabled": after})
        fac.set_cc_scenarios_summary(summary)

        self.mark_dirty()
        if notify:
            self.notify_changed()
        self._emit_input_changed({"scenario_enabled": esc_i})
        return True

    def get_scenario_enabled(self, esc: int) -> bool:
        esc_i = int(esc) if esc else 1
        if esc_i < 1:
            esc_i = 1
        fac = self.facade()
        enabled_map = fac.get_cc_scenarios_enabled() or {}
        return bool(enabled_map.get(str(esc_i), True))

    def normalize_cc_scenarios_storage(self, n_esc: int | None = None) -> bool:
        """Normaliza almacenamiento de nombres de escenarios a formato dict (sin legacy list).

        Problema histórico:
        - Algunas versiones guardaron proyecto['cc_escenarios'] como LISTA de dicts.
        - Otras partes del sistema (ProjectFacade/get_escenarios_desc) esperan un DICT {"1": "..."}.

        Esta función:
        - Convierte list -> dict y la deja persistida en el proyecto.
        - Asegura que existan claves 1..n_esc (si se entrega n_esc).
        - Devuelve True si hubo cambios.
        """
        proj = self.project()
        changed = False

        raw = proj.get("cc_escenarios", None)

        # Convertir legacy list -> dict
        if isinstance(raw, list):
            d: dict[str, str] = {}
            for i, it in enumerate(raw, start=1):
                desc = ""
                if isinstance(it, dict):
                    desc = str(it.get("desc", "") or "").strip()
                else:
                    desc = str(it or "").strip()
                if not desc:
                    desc = ""
                d[str(i)] = desc
            proj["cc_escenarios"] = d
            changed = True

        # Normalizar tipo a dict
        if not isinstance(proj.get("cc_escenarios", None), dict):
            proj["cc_escenarios"] = {}
            changed = True

        # Asegurar claves
        if n_esc is not None:
            try:
                n = int(n_esc)
            except Exception:
                n = 0
            if n > 0:
                d = proj.get("cc_escenarios") or {}
                for i in range(1, n + 1):
                    k = str(i)
                    if k not in d:
                        d[k] = ""
                        changed = True
                proj["cc_escenarios"] = d

        # Mantener facade (si usa otra key interna) actualizado best-effort
        try:
            fac = self.facade()
            d = proj.get("cc_escenarios") or {}
            if isinstance(d, dict):
                for k, v in d.items():
                    fac.update_cc_scenario_desc(str(k), str(v))
        except Exception:
            # best-effort: no romper UI por migración
            pass

        if changed:
            self.mark_dirty()
            self.notify_changed()
        return changed

    # --------- CalcService bridge (keeps current behavior) ---------
    #(keeps current behavior) ---------
    def recalc_cc_best_effort(self) -> Dict[str, Any]:
        """Recalcula C.C. y actualiza proyecto['calculated']['cc'] usando CalcService.

        Importante:
        - CalcService recibe el *data_model*, no el dict de proyecto.
        - El método disponible es recalc_cc() (no calc_cc_best_effort()).
        - Best-effort: no levanta excepción hacia la UI.
        """
        proj = self.project()
        res = self.safe_call(
            lambda: CalcService(self.data_model).recalc_cc(),
            default=None,
            title="Cálculo C.C.",
            user_message="No se pudo recalcular C.C. (best-effort).",
            log_message="CalcService.recalc_cc failed",
        )
        if not res.ok:
            return {}
        calc = proj.get("calculated")
        if not isinstance(calc, dict):
            return {}
        cc = calc.get("cc")
        return cc if isinstance(cc, dict) else {}

    # --------- Domain computations (pure-ish) ---------
    def compute_permanentes(self, *, vmin: float) -> Dict[str, Any]:
        proj = self.project()
        gabinetes = get_model_gabinetes(self.data_model)
        return compute_cc_permanentes_totals(proj, gabinetes, vmin)

    def compute_momentary(self, *, vmin: float) -> Dict[str, Any]:
        proj = self.project()
        gabinetes = get_model_gabinetes(self.data_model)
        n_esc = get_num_escenarios(proj, default=8)
        return compute_momentary_scenarios_full(proj, gabinetes, vmin, n_esc)

    def compute_random(self, *, vmin: float) -> Dict[str, Any]:
        gabinetes = get_model_gabinetes(self.data_model)
        return compute_cc_aleatorios_totals(gabinetes, vmin)

    # Aliases semánticos (ES) para mantener claridad en callers nuevos.
    def compute_momentaneos(self, *, vmin: float) -> Dict[str, Any]:
        return self.compute_momentary(vmin=vmin)

    def compute_aleatorios(self, *, vmin: float) -> Dict[str, Any]:
        return self.compute_random(vmin=vmin)

    def _find_comp_by_id(self, comp_id: str) -> Dict[str, Any] | None:
        if not comp_id:
            return None
        for gab in get_model_gabinetes(self.data_model):
            for comp in gab.get("components", []) or []:
                if comp.get("id") == comp_id:
                    return comp
        return None

    def set_random_selected(self, comp_id: str, selected: bool) -> bool:
        comp = self._find_comp_by_id(comp_id)
        if not isinstance(comp, dict):
            return False
        data = comp.setdefault("data", {})
        if data.get("cc_aleatorio_sel") == bool(selected):
            return False
        data["cc_aleatorio_sel"] = bool(selected)
        self.mark_dirty()
        self._emit_input_changed({"aleatorio_sel": True})
        return True

    def get_random_selected(self, comp_id: str) -> bool:
        comp = self._find_comp_by_id(comp_id)
        if not isinstance(comp, dict):
            return False
        data = comp.get("data", {}) or {}
        return bool(data.get("cc_aleatorio_sel", False))

    def set_momentary_flags(self, comp_id: str, incluir: bool, escenario: int) -> bool:
        comp = self._find_comp_by_id(comp_id)
        if not isinstance(comp, dict):
            return False
        data = comp.setdefault("data", {})
        old_incluir = bool(data.get("cc_mom_incluir", True))
        old_esc = int(data.get("cc_mom_escenario", 1) or 1)
        new_incluir = bool(incluir)
        new_esc = int(escenario or 1)
        if new_esc < 1:
            new_esc = 1
        if old_incluir == new_incluir and old_esc == new_esc:
            return False
        data["cc_mom_incluir"] = new_incluir
        data["cc_mom_escenario"] = new_esc
        self.mark_dirty()
        self._emit_input_changed({"momentaneo_flags": True})
        return True

    def compute_totals(self, *, vmin: float) -> Dict[str, Any]:
        """Recalcula SIEMPRE totales C.C. desde el modelo actual.

        Importante:
        - NO usa project['calculated']['cc'] como fuente de verdad.
        - Mantiene salida legacy plana para la UI actual.
        - También devuelve secciones anidadas (permanentes/momentaneos/aleatorios).
        - Actualiza el cache calculated.cc luego del recálculo.
        """
        perm_raw = self.compute_permanentes(vmin=vmin)
        mom_raw = self.compute_momentaneos(vmin=vmin)
        rnd_raw = self.compute_aleatorios(vmin=vmin)

        perm_raw = perm_raw if isinstance(perm_raw, dict) else {}
        mom_raw = mom_raw if isinstance(mom_raw, dict) else {}
        rnd_raw = rnd_raw if isinstance(rnd_raw, dict) else {}

        permanentes = {
            "p_total": float(perm_raw.get("p_total", 0.0) or 0.0),
            "p_perm": float(perm_raw.get("p_perm", 0.0) or 0.0),
            "p_mom": float(perm_raw.get("p_mom", 0.0) or 0.0),
            "i_perm": float(perm_raw.get("i_perm", 0.0) or 0.0),
            "i_mom": float(perm_raw.get("i_mom", 0.0) or 0.0),
        }

        # Momentáneos: fuente principal por escenarios; totales rápidos del escenario 1.
        mom_scn1 = None
        if isinstance(mom_raw.get(1), dict):
            mom_scn1 = mom_raw.get(1)
        elif isinstance(mom_raw.get("1"), dict):
            mom_scn1 = mom_raw.get("1")
        else:
            mom_scn1 = {}

        momentaneos = {
            "scenarios": mom_raw,
            "p_total": float(mom_scn1.get("p_total", 0.0) or 0.0),
            "i_total": float(mom_scn1.get("i_total", 0.0) or 0.0),
        }

        aleatorios = {
            "p_sel": float(rnd_raw.get("p_sel", 0.0) or 0.0),
            "i_sel": float(rnd_raw.get("i_sel", 0.0) or 0.0),
        }

        # Salida plana legacy (la usa la pestaña Permanentes para labels inferiores).
        flat = {
            "p_total": float(permanentes["p_total"]),
            "i_total": float(permanentes["i_perm"] + permanentes["i_mom"]),
            "p_perm": float(permanentes["p_perm"]),
            "i_perm": float(permanentes["i_perm"]),
            "p_mom": float(permanentes["p_mom"]),
            "i_mom": float(permanentes["i_mom"]),
            "p_sel": float(aleatorios["p_sel"]),
            "i_sel": float(aleatorios["i_sel"]),
        }

        # Mantener cache sincronizado (nunca como source-of-truth).
        proj = self.project()
        if isinstance(proj, dict):
            calc = proj.setdefault("calculated", {})
            if isinstance(calc, dict):
                cc = calc.setdefault("cc", {})
                if isinstance(cc, dict):
                    cc["permanentes"] = dict(permanentes)
                    cc["momentaneos"] = dict(momentaneos)
                    cc["aleatorios"] = dict(aleatorios)
                    cc["summary"] = {
                        "p_total": flat["p_total"],
                        "i_total": flat["i_total"],
                        "p_perm": flat["p_perm"],
                        "i_perm": flat["i_perm"],
                        "p_mom": flat["p_mom"],
                        "i_mom": flat["i_mom"],
                        "p_sel": flat["p_sel"],
                        "i_sel": flat["i_sel"],
                    }

        out: Dict[str, Any] = dict(flat)
        out["permanentes"] = permanentes
        out["momentaneos"] = momentaneos
        out["aleatorios"] = aleatorios
        return out
