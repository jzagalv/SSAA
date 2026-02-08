# -*- coding: utf-8 -*-
"""Text encoding helpers for mojibake repair."""
from __future__ import annotations

from typing import Any


_MOJIBAKE_MARKERS = ("Ã", "Â", "¤", "�")


def fix_mojibake(s: str) -> str:
    if not isinstance(s, str):
        return s
    if not s:
        return s
    if any(m in s for m in _MOJIBAKE_MARKERS):
        try:
            return s.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
        except Exception:
            return s
    return s


def fix_mojibake_deep(obj: Any) -> Any:
    if isinstance(obj, str):
        return fix_mojibake(obj)
    if isinstance(obj, list):
        return [fix_mojibake_deep(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(fix_mojibake_deep(v) for v in obj)
    if isinstance(obj, dict):
        return {fix_mojibake_deep(k): fix_mojibake_deep(v) for k, v in obj.items()}
    return obj
