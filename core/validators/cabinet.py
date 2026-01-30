# -*- coding: utf-8 -*-
"""Validations for component placement and basic consumption data."""

from __future__ import annotations

from typing import List

from core.types import Issue, Severity


def _to_float(x, default=0.0):
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return default


def validate_cabinet(dm) -> List[Issue]:
    inst = getattr(dm, "instalaciones", {}) or {}
    gabinetes = list(inst.get("gabinetes") or [])
    issues: List[Issue] = []

    for g in gabinetes:
        gtag = str(g.get("tag") or g.get("nombre") or "").strip()
        comps = list(g.get("components") or [])
        for c in comps:
            data = c.get("data") or {}
            name = str(c.get("name") or data.get("name") or "").strip() or "(sin nombre)"

            # Power must be numeric if present
            p_w = data.get("potencia_w")
            if p_w not in (None, "", "----"):
                pw = _to_float(p_w, default=None)
                if pw is None:
                    issues.append(Issue(code="COMP_PW_INVALID", message=f"{gtag}: potencia_w inválida en '{name}'.", severity=Severity.WARNING, context=gtag))

            # Basic geometry sanity
            size = c.get("size") or {}
            w = _to_float(size.get("w"), default=0.0)
            h = _to_float(size.get("h"), default=0.0)
            if w < 0 or h < 0:
                issues.append(Issue(code="COMP_SIZE_NEG", message=f"{gtag}: tamaño negativo en '{name}'.", severity=Severity.WARNING, context=gtag))

    return issues
