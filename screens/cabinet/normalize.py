# -*- coding: utf-8 -*-
"""Normalización de datos de componente (Compatibilidad).

Este módulo NO depende de Qt. Su objetivo es mantener la compatibilidad con
proyectos/librerías antiguas donde cambian nombres de claves (p.ej. potencia_cc).
"""

from __future__ import annotations

from typing import Any, Dict


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "si", "sí", "y")
    return bool(v)


def normalize_comp_data(data: Dict[str, Any] | None) -> Dict[str, Any]:
    """Normaliza el dict `data` de un componente.

    - Asegura claves base (tag, marca, modelo).
    - Unifica potencia en W en `potencia_w` (desde potencia_cc/potencia/P_W).
    - Unifica potencia en VA en `potencia_va` (desde P_VA/potencia_va).
    - Normaliza `usar_va` a bool.
    - Asegura alimentador/tipo_consumo/fase/origen.
    """
    d: Dict[str, Any] = dict(data or {})

    # claves base
    d.setdefault("tag", d.get("TAG", ""))
    d.setdefault("marca", d.get("brand", d.get("Marca", "")))
    d.setdefault("modelo", d.get("model", d.get("Modelo", "")))

    # potencia W (compat)
    if "potencia_w" not in d:
        if "potencia_cc" in d:
            d["potencia_w"] = d.get("potencia_cc")
        elif "potencia" in d:
            d["potencia_w"] = d.get("potencia")
        elif "P_W" in d:
            d["potencia_w"] = d.get("P_W")
        else:
            d["potencia_w"] = ""

    # potencia VA (compat)
    if "potencia_va" not in d:
        if "P_VA" in d:
            d["potencia_va"] = d.get("P_VA")
        else:
            d["potencia_va"] = d.get("potencia_va", "")

    # usar_va (acepta str/num/bool)
    d["usar_va"] = _truthy(d.get("usar_va", False))

    # alimentador / tipo / fase / origen
    d.setdefault("alimentador", d.get("feed_type", "General"))
    d.setdefault("tipo_consumo", d.get("tipo", "C.C. permanente"))
    d.setdefault("fase", d.get("fase", "1F"))
    d.setdefault("origen", d.get("origen", "Genérico"))

    return d
