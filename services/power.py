# -*- coding: utf-8 -*-
"""
services/power.py

Helpers de interpretación de potencia de entrada (dominio liviano).
No depende de PyQt.
"""

from __future__ import annotations
from typing import Optional, Tuple, Dict, Any


def get_ac_power_input(comp_data: Dict[str, Any]) -> Tuple[Optional[float], str]:
    """
    Devuelve el valor de potencia AC ingresada y su tipo:
    - Si usar_va=True => (potencia_va, "VA")
    - Si usar_va=False => (potencia_w, "W")

    Nota: puede devolver (None, "W/VA") si el usuario no ingresó el valor.
    La validación real debe hacerse en capa de cálculo.
    """
    if comp_data.get("usar_va"):
        return comp_data.get("potencia_va"), "VA"
    return comp_data.get("potencia_w"), "W"
