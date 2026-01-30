# -*- coding: utf-8 -*-
"""Validations for CC calculation inputs."""

from __future__ import annotations

from typing import List

from core.types import Issue, Severity


def validate_cc(dm) -> List[Issue]:
    proyecto = getattr(dm, "proyecto", {}) or {}
    issues: List[Issue] = []

    vmin = proyecto.get("v_cc") or proyecto.get("vcc") or proyecto.get("tension_cc")
    try:
        vmin = float(str(vmin).replace(",", "."))
    except Exception:
        vmin = 0.0
    if vmin <= 0:
        issues.append(Issue(code="CC_VCC_INVALID", message="Vcc para cálculo C.C. no está definida o es inválida.", severity=Severity.ERROR, context="v_cc"))

    # Utilization percent default
    pct = proyecto.get("cc_pct_global", proyecto.get("cc_pct", 100.0))
    try:
        pct = float(str(pct).replace(",", "."))
    except Exception:
        pct = 100.0
    if pct < 0 or pct > 100:
        issues.append(Issue(code="CC_PCT_RANGE", message="Porcentaje de utilización C.C. debe estar entre 0 y 100.", severity=Severity.WARNING, context="cc_pct"))

    return issues
