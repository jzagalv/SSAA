# -*- coding: utf-8 -*-
"""CC schema contract helpers (no UI)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

log = logging.getLogger(__name__)

SCHEMA_VERSION = 3


def normalize_project(proj: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure expected keys and types exist on the project dict."""
    if not isinstance(proj, dict):
        proj = {}

    # cc_escenarios (names)
    cc_esc = proj.get("cc_escenarios")
    if isinstance(cc_esc, list):
        cc_new: Dict[str, str] = {}
        for i, it in enumerate(cc_esc, start=1):
            if isinstance(it, dict):
                desc = str(it.get("desc") or "").strip()
            else:
                desc = str(it or "").strip()
            if not desc:
                desc = ""
            cc_new[str(i)] = desc
        cc_esc = cc_new
    if not isinstance(cc_esc, dict):
        cc_esc = {}
    proj["cc_escenarios"] = cc_esc

    # calculated.cc containers
    calc = proj.get("calculated")
    if not isinstance(calc, dict):
        calc = {}
    cc_calc = calc.get("cc")
    if not isinstance(cc_calc, dict):
        cc_calc = {}
    if not isinstance(cc_calc.get("summary"), dict):
        cc_calc["summary"] = {}
    if not isinstance(cc_calc.get("scenarios_totals"), dict):
        cc_calc["scenarios_totals"] = {}
    calc["cc"] = cc_calc
    proj["calculated"] = calc

    # legacy summary container (names list)
    summary = proj.get("cc_scenarios_summary")
    if summary is not None and not isinstance(summary, list):
        proj["cc_scenarios_summary"] = []

    return proj


def ensure_cc_scenarios(proj: Dict[str, Any], n_esc: int) -> Dict[str, str]:
    """Ensure cc.scenarios has keys 1..n_esc without overwriting existing names."""
    proj = normalize_project(proj)
    scenarios = proj.get("cc_escenarios", {})

    try:
        n = int(n_esc or 1)
    except Exception:
        n = 1
    if n < 1:
        n = 1

    for i in range(1, n + 1):
        k = str(i)
        if k not in scenarios:
            scenarios[k] = ""

    proj["cc_escenarios"] = scenarios
    return scenarios


def ensure_calculated_cc(proj: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure calculated.cc.summary and calculated.cc.scenarios_totals exist."""
    proj = normalize_project(proj)
    return proj.get("calculated", {}).get("cc", {})


def validate_project(proj: Dict[str, Any]) -> List[str]:
    """Return a list of soft validation messages (log-only)."""
    issues: List[str] = []
    if not isinstance(proj, dict):
        issues.append("proyecto is not a dict")
        return issues

    cc_esc = proj.get("cc_escenarios")
    if not isinstance(cc_esc, dict):
        issues.append("proyecto.cc_escenarios missing or invalid")

    calc = proj.get("calculated")
    if not isinstance(calc, dict):
        issues.append("proyecto.calculated missing or invalid")
    else:
        cc_calc = calc.get("cc")
        if not isinstance(cc_calc, dict):
            issues.append("proyecto.calculated.cc missing or invalid")
        else:
            if not isinstance(cc_calc.get("summary"), dict):
                issues.append("proyecto.calculated.cc.summary missing or invalid")
            if not isinstance(cc_calc.get("scenarios_totals"), dict):
                issues.append("proyecto.calculated.cc.scenarios_totals missing or invalid")

    return issues
