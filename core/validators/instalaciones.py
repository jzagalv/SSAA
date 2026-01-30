# -*- coding: utf-8 -*-
"""Validations for instalaciones (salas/ubicaciones + gabinetes)."""

from __future__ import annotations

from collections import Counter
from typing import List

from core.types import Issue, Severity


def validate_instalaciones(dm) -> List[Issue]:
    inst = getattr(dm, "instalaciones", {}) or {}
    ubicaciones = list(inst.get("ubicaciones") or [])
    gabinetes = list(inst.get("gabinetes") or [])

    issues: List[Issue] = []

    # Ubicaciones IDs set
    ub_ids = {str(u.get("id") or "").strip() for u in ubicaciones if str(u.get("id") or "").strip()}

    # Cabinet tags unique
    tags = [str(g.get("tag") or "").strip() for g in gabinetes]
    for tag, cnt in Counter([t for t in tags if t]).items():
        if cnt > 1:
            issues.append(Issue(code="CAB_DUP_TAG", message=f"Tag de gabinete duplicado: '{tag}' ({cnt} veces).", severity=Severity.ERROR, context=tag))
    for idx, g in enumerate(gabinetes):
        tag = str(g.get("tag") or "").strip()
        if not tag:
            issues.append(Issue(code="CAB_TAG_EMPTY", message=f"Gabinete #{idx+1} no tiene TAG.", severity=Severity.WARNING, context="gabinetes"))
        uid = str(g.get("ubicacion_id") or "").strip()
        if uid and uid not in ub_ids:
            issues.append(Issue(code="CAB_UBICACION_MISSING", message=f"Gabinete '{tag or g.get('nombre','')}' referencia una ubicación inexistente.", severity=Severity.ERROR, context=uid))

    return issues
