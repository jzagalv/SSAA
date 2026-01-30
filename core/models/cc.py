# -*- coding: utf-8 -*-
"""Models for DC (C.C.) consumption calculations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CCLoadRow:
    """A single DC load row used by the CC calculation core.

    This is intentionally minimal; extra fields can be added when needed.
    """

    tag: str
    description: str
    power_w: float
    pct_util: float = 100.0


@dataclass(frozen=True)
class CCSummary:
    """High-level CC totals (permanent + derived momentary + currents)."""

    p_total_w: float
    p_perm_w: float
    p_mom_w: float
    i_perm_a: float
    i_mom_a: float
