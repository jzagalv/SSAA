# -*- coding: utf-8 -*-
"""Base controllers (no-Qt).

This project mixes two types of controllers:

1) "Pure" controllers: operate on DataModel/proyecto and do not depend on Qt.
2) Screen controllers: hold a reference to a Qt screen but should still handle
   errors/dirty/notifications consistently.

This module provides a minimal shared base with:
- mark_dirty()
- notify_changed()
- safe_call() (best-effort execution with logging)

Keep this module free of PyQt imports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from core.sections import Section

log = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class SafeCallResult:
    ok: bool
    value: Any = None
    error: Optional[BaseException] = None


class BaseController:
    """Shared helpers for controllers.

    Parameters
    ----------
    data_model:
        DataModel-like object. Must provide optional:
        - mark_dirty(bool)
        - notify_section_changed(Section)
        - proyecto (dict)
    section:
        Default Section to notify.
    screen:
        Optional screen reference (Qt widget). Used only to discover data_model
        if not explicitly provided.
    on_error:
        Optional callable to surface errors to UI. It receives a short title and
        message. Kept generic (no Qt types).
    """

    def __init__(
        self,
        data_model: Any = None,
        *,
        section: Optional[Section] = None,
        screen: Any = None,
        on_error: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self._data_model = data_model
        self._screen = screen
        self._section = section
        self._on_error = on_error

    # --------- discovery ---------
    @property
    def data_model(self) -> Any:
        if self._data_model is not None:
            return self._data_model
        if self._screen is not None:
            return getattr(self._screen, "data_model", None)
        return None

    @property
    def section(self) -> Optional[Section]:
        return self._section

    def set_on_error(self, on_error: Optional[Callable[[str, str], None]]) -> None:
        self._on_error = on_error

    # --------- common actions ---------
    def mark_dirty(self) -> None:
        dm = self.data_model
        if dm is None:
            return
        if hasattr(dm, "mark_dirty"):
            try:
                dm.mark_dirty(True)
            except Exception:
                # never crash UI for dirty flag
                log.debug("mark_dirty ignored exception", exc_info=True)

    def notify_changed(self, section: Optional[Section] = None) -> None:
        dm = self.data_model
        if dm is None:
            return
        sec = section or self._section
        if sec is None:
            return
        if hasattr(dm, "notify_section_changed"):
            try:
                dm.notify_section_changed(sec)
            except Exception:
                log.debug("notify_section_changed ignored exception", exc_info=True)

    # --------- safe execution ---------
    def safe_call(
        self,
        fn: Callable[..., T],
        *args: Any,
        default: Optional[T] = None,
        title: str = "Error",
        user_message: str = "Ocurrió un error inesperado.",
        log_message: Optional[str] = None,
        **kwargs: Any,
    ) -> SafeCallResult:
        """Run fn(*args, **kwargs) and never raise.

        - Logs exception with context.
        - Optionally surfaces a short message to UI via on_error callback.
        """
        try:
            value = fn(*args, **kwargs)
            return SafeCallResult(ok=True, value=value)
        except Exception as e:
            if log_message:
                log.exception(log_message)
            else:
                log.exception("safe_call caught exception")
            if self._on_error:
                try:
                    self._on_error(title, user_message)
                except Exception:
                    log.debug("on_error callback failed", exc_info=True)
            return SafeCallResult(ok=False, value=default, error=e)
