# -*- coding: utf-8 -*-
"""Pure CC calculations.

NOTE: This module must not depend on PyQt or the app's DataModel.
"""

from __future__ import annotations

from typing import Iterable

from core.models.cc import CCLoadRow, CCSummary


def compute_cc_summary(rows: Iterable[CCLoadRow], vmin: float) -> CCSummary:
    """Compute basic CC totals.

    - p_total_w: sum of effective powers
    - p_perm_w : sum(power * pct/100)
    - p_mom_w  : sum(power * (100-pct)/100)
    Currents are derived using vmin.
    """
    v = float(vmin) if (vmin or 0) > 0 else 1.0
    p_total = 0.0
    p_perm = 0.0
    p_mom = 0.0
    for r in rows or []:
        p = float(getattr(r, "power_w", 0.0) or 0.0)
        if p <= 0:
            continue
        pct = float(getattr(r, "pct_util", 100.0) or 0.0)
        if pct < 0:
            pct = 0.0
        if pct > 100:
            pct = 100.0
        p_total += p
        p_perm += p * (pct / 100.0)
        p_mom += p * ((100.0 - pct) / 100.0)

    return CCSummary(
        p_total_w=float(p_total),
        p_perm_w=float(p_perm),
        p_mom_w=float(p_mom),
        i_perm_a=float(p_perm / v),
        i_mom_a=float(p_mom / v),
    )
