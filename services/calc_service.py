# -*- coding: utf-8 -*-
"""Calculation orchestration service.

This service provides a stable API for recalculating project sections
and storing derived results back into the project dict.

For now, CC calculations are computed using the existing domain module
(`domain.cc_consumption`) to keep behavior identical. Over time, we can
progressively migrate logic into `core/`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from core.calculations.cc import compute_cc_summary
from core.models.cc import CCLoadRow

from domain.cc_consumption import (
    get_model_gabinetes,
    get_vcc_for_currents,
    get_num_escenarios,
    compute_cc_permanentes_totals,
    compute_momentary_scenarios_full,
    compute_cc_aleatorios_totals,
)
from domain.cc_consumption import _normalize_comp_data, _effective_power_w, _pct_for_permanent, _clamp

from core.calculations.bank_charger import compute_bank_charger as core_compute_bank_charger


log = logging.getLogger(__name__)


class CalcService:
    """Centralized calculation service."""

    def __init__(self, data_model):
        self.data_model = data_model
        self.runtime_cache: Dict[str, Any] = {}

    def recalc_cc(self) -> Dict[str, Any]:
        """Recalculate CC derived values and store them under proyecto['calculated']['cc'].

        We compute a pure-core summary (serializable) and keep the legacy detailed blocks
        for backward compatibility with existing screens.
        """
        dm = self.data_model
        proyecto: Dict[str, Any] = getattr(dm, "proyecto", {}) or {}
        gabinetes = get_model_gabinetes(dm)

        vmin = float(get_vcc_for_currents(proyecto) or 0.0)
        if vmin <= 0:
            vmin = 1.0

        # --- Pure-core summary for permanentes ---
        rows: list[CCLoadRow] = []
        pct_global = float(proyecto.get("cc_pct_global", proyecto.get("cc_pct", 100.0)) or 100.0)
        for cab in (gabinetes or []):
            for comp in (cab.get("components", []) or []):
                data = _normalize_comp_data(comp.get("data", {}) or {})
                tipo = str(data.get("tipo_consumo", "") or "").strip()
                if tipo != "C.C. permanente":
                    continue
                p_eff = float(_effective_power_w(data) or 0.0)
                if p_eff <= 0:
                    continue
                pct = float(_pct_for_permanent(proyecto, data) or pct_global)
                pct = float(_clamp(pct, 0.0, 100.0))
                rows.append(
                    CCLoadRow(
                        tag=str(data.get("tag", "") or ""),
                        description=str(data.get("descripcion", data.get("desc", "")) or ""),
                        power_w=p_eff,
                        pct_util=pct,
                    )
                )

        summary = compute_cc_summary(rows, vmin=vmin)
        summary_dict = {
            "p_total_w": summary.p_total_w,
            "p_perm_w": summary.p_perm_w,
            "p_mom_w": summary.p_mom_w,
            "i_perm_a": summary.i_perm_a,
            "i_mom_a": summary.i_mom_a,
            "vmin": float(vmin),
        }

        # --- Legacy blocks (kept for existing UI sections) ---
        perm = compute_cc_permanentes_totals(proyecto, gabinetes, vmin)
        n_esc = int(get_num_escenarios(proyecto) or 1)
        mom = compute_momentary_scenarios_full(proyecto, gabinetes, vmin, n_esc)
        ale = compute_cc_aleatorios_totals(gabinetes, vmin)

        out: Dict[str, Any] = {
            "summary": summary_dict,
            "permanentes": perm,
            "momentaneos": mom,
            "aleatorios": ale,
        }

        calc = proyecto.get("calculated")
        if not isinstance(calc, dict):
            calc = {}
            proyecto["calculated"] = calc
        calc["cc"] = out
        return out

    
    def recalc_bank_charger(
        self,
        *,
        periods: list,
        rnd: Dict[str, Any] | None,
        i_perm: float,
    ) -> Dict[str, Any]:
        """Recalculate Bank/Charger sizing.

        Stores a *serializable* summary under proyecto['calculated']['bank_charger'] and keeps
        the full runtime bundle in `self.runtime_cache['bank_charger_bundle']`.
        """
        proyecto: Dict[str, Any] = getattr(self.data_model, "proyecto", {}) or {}

        bundle, summary = core_compute_bank_charger(
            proyecto=proyecto,
            periods=periods,
            rnd=rnd,
            i_perm=float(i_perm or 0.0),
        )

        self.runtime_cache["bank_charger_bundle"] = bundle

        calc = proyecto.get("calculated")
        if not isinstance(calc, dict):
            calc = {}
            proyecto["calculated"] = calc
        calc["bank_charger"] = summary
        return {"summary": summary, "bundle": bundle}


    def recalc_all(self) -> None:
        """Recalculate all supported sections.

        This is intentionally best-effort and should never crash the UI.
        """
        try:
            self.recalc_cc()
        except Exception:
            log.debug("Failed to recalc CC (best-effort).", exc_info=True)

