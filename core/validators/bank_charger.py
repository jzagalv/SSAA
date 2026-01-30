# -*- coding: utf-8 -*-
"""Validations for Bank/Charger sizing inputs."""

from __future__ import annotations

from typing import List

from core.types import Issue, Severity


def validate_bank_charger(dm) -> List[Issue]:
    proyecto = getattr(dm, "proyecto", {}) or {}
    issues: List[Issue] = []

    # IEEE 485 Kt table presence (not mandatory, but affects accuracy)
    kt = proyecto.get("ieee485_kt")
    if not isinstance(kt, dict) or not kt:
        issues.append(Issue(code="BC_KT_MISSING", message="No hay tabla IEEE485 Kt cargada (se usarán defaults si existen).", severity=Severity.INFO, context="ieee485_kt"))

    # Nominal CC voltage
    v = proyecto.get("v_cc") or proyecto.get("vcc") or proyecto.get("tension_cc")
    try:
        v = float(str(v).replace(",", "."))
    except Exception:
        v = 0.0
    if v <= 0:
        issues.append(Issue(code="BC_VCC_INVALID", message="No se puede dimensionar banco/cargador sin Vcc válido.", severity=Severity.ERROR, context="v_cc"))

    return issues
