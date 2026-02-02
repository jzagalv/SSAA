# -*- coding: utf-8 -*-
"""Pure compute orchestrator core (no UI dependencies)."""
from __future__ import annotations

from typing import Optional, Set
import time


class ComputeOrchestratorCore:
    """Debounced dirty tracker for compute sections."""

    def __init__(self, *, debounce_ms: int = 200) -> None:
        self._debounce_ms = int(debounce_ms)
        self._dirty: Set[object] = set()
        self._last_mark_ts: float = 0.0

    def mark_dirty(self, section, *, now: Optional[float] = None) -> None:
        self._dirty.add(section)
        self._last_mark_ts = float(time.time() if now is None else now)

    def should_run(self, *, now: Optional[float] = None) -> bool:
        if not self._dirty:
            return False
        ts = float(time.time() if now is None else now)
        return (ts - self._last_mark_ts) * 1000.0 >= float(self._debounce_ms)

    def pop_dirty(self) -> Set[object]:
        dirty = set(self._dirty)
        self._dirty.clear()
        return dirty

    def has_dirty(self) -> bool:
        return bool(self._dirty)


def is_stale_result(current_id: int, result_id: int) -> bool:
    """Return True if a compute result should be discarded."""
    try:
        return int(result_id) != int(current_id)
    except Exception:
        return True
