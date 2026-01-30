# -*- coding: utf-8 -*-
"""Pure bank+charger sizing orchestration (no PyQt).

This wraps the existing domain engine and returns:
  - the full runtime bundle (not JSON-serializable)
  - a compact serializable summary dict suitable for proyecto['calculated']
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional, Tuple

from domain.bank_charger_engine import run_bank_charger_engine
from domain.ieee485 import build_ieee485
from domain.selection import compute_bank_selection, compute_charger_selection


def _as_serializable(obj: Any) -> Any:
    if obj is None:
        return None
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _as_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_as_serializable(v) for v in obj]
    # fallback: best effort
    return str(obj)


def compute_bank_charger(
    *,
    proyecto: Dict[str, Any],
    periods: List[Dict[str, Any]],
    rnd: Optional[Dict[str, Any]],
    i_perm: float,
) -> Tuple[Any, Dict[str, Any]]:
    """Compute bank+charger bundle + serializable summary."""

    kt_store = dict((proyecto or {}).get("ieee485_kt", {}) or {})

    bundle = run_bank_charger_engine(
        proyecto=proyecto or {},
        periods=periods or [],
        rnd=rnd,
        kt_store=kt_store,
        i_perm=float(i_perm or 0.0),
        build_ieee485_fn=build_ieee485,
        compute_bank_selection_fn=compute_bank_selection,
        compute_charger_selection_fn=compute_charger_selection,
    )

    summary: Dict[str, Any] = {
        "missing_kt_keys": list(getattr(bundle, "missing_kt_keys", []) or []),
        "warnings": list(getattr(bundle, "warnings", []) or []),
        "bank": _as_serializable(getattr(bundle, "bank", None)),
        "charger": _as_serializable(getattr(bundle, "charger", None)),
    }
    return bundle, summary
