# -*- coding: utf-8 -*-
"""Project-level validations (pure)."""

from __future__ import annotations

from typing import List

from core.types import Issue, Severity


def validate_project(dm) -> List[Issue]:
    proyecto = getattr(dm, "proyecto", {}) or {}
    issues: List[Issue] = []

    # Common fields that frequently impact calculations.
    required = [
        ("nombre_proyecto", "Nombre de proyecto"),
        ("cliente", "Cliente"),
    ]
    for key, label in required:
        val = str(proyecto.get(key, "") or "").strip()
        if not val:
            issues.append(Issue(code="PROJ_MISSING_FIELD", message=f"Falta {label} en 'Proyecto'.", severity=Severity.WARNING, context=key))

    # Voltages for CC.
    v = proyecto.get("v_cc") or proyecto.get("vcc") or proyecto.get("tension_cc")
    try:
        v = float(str(v).replace(",", ".")) if v not in (None, "") else 0.0
    except Exception:
        v = 0.0
    if v <= 0:
        issues.append(Issue(code="PROJ_VCC_INVALID", message="La tensión C.C. (Vcc/V_CC) no está definida o es inválida.", severity=Severity.WARNING, context="v_cc"))

    return issues
