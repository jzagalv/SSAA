# -*- coding: utf-8 -*-
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable


class DirtyTracker:
    """Centralized unsaved-changes state (best-effort, UI-agnostic)."""

    def __init__(self, initial_dirty: bool = False) -> None:
        self.is_dirty = bool(initial_dirty)
        self._suspend_depth = 0
        self.last_change_summary = ""

    @property
    def suspended(self) -> bool:
        return bool(self._suspend_depth > 0)

    def mark_dirty(self, reason: str = "", keys: Iterable[str] | None = None) -> None:
        if self.suspended:
            return
        self.is_dirty = True
        parts = []
        if reason:
            parts.append(str(reason))
        if keys:
            parts.append(",".join(str(k) for k in keys))
        self.last_change_summary = " | ".join(parts)

    def clear_dirty(self) -> None:
        self.is_dirty = False
        self.last_change_summary = ""

    def sync_from_model(self, dirty: bool, *, force: bool = False) -> None:
        if self.suspended and not force:
            return
        self.is_dirty = bool(dirty)
        if not self.is_dirty:
            self.last_change_summary = ""

    def suspend(self) -> None:
        self._suspend_depth += 1

    def resume(self) -> None:
        if self._suspend_depth > 0:
            self._suspend_depth -= 1

    @contextmanager
    def suspend_tracking(self):
        self.suspend()
        try:
            yield
        finally:
            self.resume()
