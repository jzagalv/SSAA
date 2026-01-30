# -*- coding: utf-8 -*-
"""Bank/Charger domain service (UI-agnostic).

Keeps heavy calculations out of screens.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Tuple

from services.calculations import compute_battery_sizing


def compute_and_update_project(proyecto: Dict[str, Any]) -> Tuple[Any, bool]:
    """Run sizing and persist key outputs into *proyecto*.

    Returns:
        (result, changed) where *changed* indicates v_max/v_min changed.
    """
    res = compute_battery_sizing({"proyecto": proyecto})

    prev_vmax = proyecto.get("v_max")
    prev_vmin = proyecto.get("v_min")

    if getattr(res, "v_max", None) is not None:
        proyecto["v_max"] = res.v_max
    if getattr(res, "v_min", None) is not None:
        proyecto["v_min"] = res.v_min

    changed = (prev_vmax != proyecto.get("v_max")) or (prev_vmin != proyecto.get("v_min"))
    return res, changed
