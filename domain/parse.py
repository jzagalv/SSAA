# -*- coding: utf-8 -*-
"""
domain/parse.py

Helpers únicos de parsing/normalización para valores numéricos y celdas tipo Excel.
Objetivo:
- Evitar duplicación de safe_float/_as_float por módulos.
- Ser tolerante a formatos típicos en Chile: "1.234,56" o "1234,56".
"""

from __future__ import annotations

from typing import Any, Optional


_DASH_TOKENS = {"—", "–", "-", "--", "---", "----", "— —", "—-", "-—"}


def is_blank(val: Any, allow_dash: bool = True) -> bool:
    """True si el valor debe tratarse como 'vacío'."""
    if val is None:
        return True

    # Nota: bool es subclass de int; aquí NO se considera blank.
    if isinstance(val, (int, float)):
        return False

    s = str(val).strip()
    if s == "":
        return True

    if allow_dash:
        if s in _DASH_TOKENS:
            return True
        # Strings compuestos solo por guiones/dashes
        if all(ch in "—–-" for ch in s):
            return True

    return False


def to_float(val: Any, default: Optional[float] = None, allow_dash: bool = True) -> Optional[float]:
    """
    Convierte a float de forma tolerante.
    - Acepta coma decimal.
    - Maneja miles tipo "1.234,56" o "1,234.56".
    - Si val es blank -> default.
    """
    if is_blank(val, allow_dash=allow_dash):
        return default

    if isinstance(val, bool):
        # Por seguridad: evitar que True/False se conviertan en 1.0/0.0 sin querer.
        return default

    if isinstance(val, (int, float)):
        try:
            return float(val)
        except Exception:
            return default

    s = str(val).strip()

    # Quitar espacios intermedios (p.ej. "1 234,5")
    s = s.replace(" ", "")

    # Normalización miles/decimal
    if "," in s and "." in s:
        # Heurística: el separador decimal suele ser el último que aparece.
        if s.rfind(",") > s.rfind("."):
            # "1.234,56" -> "1234.56"
            s = s.replace(".", "").replace(",", ".")
        else:
            # "1,234.56" -> "1234.56"
            s = s.replace(",", "")
    else:
        s = s.replace(",", ".")

    try:
        return float(s)
    except Exception:
        return default
