# -*- coding: utf-8 -*-
"""Simple event bus for app-level refresh routing (no UI dependency)."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Type


@dataclass(frozen=True)
class MetadataChanged:
    section: Any
    fields: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class InputChanged:
    section: Any
    fields: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ModelChanged:
    section: Any
    reason: Optional[str] = None


@dataclass(frozen=True)
class Computed:
    section: Any
    reason: str = "auto"
    timestamp: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ComputeStarted:
    section: Any
    reason: str = "auto"
    timestamp: float = field(default_factory=time.time)


class EventBus:
    """Minimal in-process event bus (best-effort)."""

    def __init__(self) -> None:
        self._subs: Dict[Type[Any], List[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: Type[Any], callback: Callable[[Any], None]) -> None:
        self._subs.setdefault(event_type, []).append(callback)

    def emit(self, event: Any) -> None:
        for cb in list(self._subs.get(type(event), []) or []):
            try:
                cb(event)
            except Exception:
                # Best-effort: never crash UI for event handlers
                logging.getLogger(__name__).debug("Event handler failed.", exc_info=True)
