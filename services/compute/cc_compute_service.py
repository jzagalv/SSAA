# -*- coding: utf-8 -*-
"""CC compute service (pure, no UI dependencies)."""
from __future__ import annotations

from typing import Any, Dict

from domain.cc_consumption import (
    compute_cc_permanentes_totals,
    compute_momentary_scenarios_full,
    compute_cc_aleatorios_totals,
    get_num_escenarios,
    get_vcc_for_currents,
)


class CCComputeService:
    def compute(self, project_dict: Dict[str, Any]) -> Dict[str, Any]:
        proj = project_dict or {}
        instalaciones = proj.get("instalaciones") if isinstance(proj, dict) else {}
        gabinetes = []
        if isinstance(instalaciones, dict):
            gabinetes = instalaciones.get("gabinetes") or []
        if not isinstance(gabinetes, list):
            gabinetes = []

        vmin = float(get_vcc_for_currents(proj))
        n_esc = int(get_num_escenarios(proj, default=1))

        perm = compute_cc_permanentes_totals(proj, gabinetes, vmin)
        scenarios = compute_momentary_scenarios_full(proj, gabinetes, vmin, n_esc)
        rnd = compute_cc_aleatorios_totals(gabinetes, vmin)

        p_mom = 0.0
        i_mom = 0.0
        by_scenario: Dict[str, Dict[str, float]] = {}
        for k in range(1, n_esc + 1):
            d = scenarios.get(k, {}) if isinstance(scenarios, dict) else {}
            p = float(d.get("p_total", 0.0) or 0.0)
            i = float(d.get("i_total", 0.0) or 0.0)
            p_mom += p
            i_mom += i
            by_scenario[str(k)] = {"p_total": p, "i_total": i}

        totals = {
            "p_total": float(perm.get("p_total", 0.0) or 0.0) + float(p_mom),
            "i_total": float(perm.get("i_perm", 0.0) or 0.0) + float(i_mom),
            "p_perm": float(perm.get("p_perm", 0.0) or 0.0),
            "i_perm": float(perm.get("i_perm", 0.0) or 0.0),
            "p_mom": float(p_mom),
            "i_mom": float(i_mom),
            # Tail derived from permanentes only (used by Bank/Charger L2 profile logic).
            "p_mom_perm": float(perm.get("p_mom", 0.0) or 0.0),
            "i_mom_perm": float(perm.get("i_mom", 0.0) or 0.0),
            "p_sel": float(rnd.get("p_sel", 0.0) or 0.0),
            "i_sel": float(rnd.get("i_sel", 0.0) or 0.0),
        }

        return {
            "vmin": float(vmin),
            "totals": totals,
            "by_scenario": by_scenario,
        }
