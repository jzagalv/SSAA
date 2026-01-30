# -*- coding: utf-8 -*-
"""ui/common/guards.py

Small guard helpers for Qt signals/slots and generic callbacks.

Goals:
- Prevent incremental refactors from crashing the app (missing handlers, etc.)
- Provide a single place to implement "best effort" connections and safe calls.
- Leave a trace (logging) instead of silent failures.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, TypeVar

from . import dialogs

log = logging.getLogger(__name__)
T = TypeVar("T")


def connect_if_callable(signal: Any, handler: Any, *, name: str = "handler") -> bool:
    """Connect *signal* to *handler* only if it's callable.

    Returns True if connected, False otherwise.
    """
    if callable(handler):
        try:
            signal.connect(handler)
            return True
        except Exception:
            log.error("Failed to connect signal to %s", name, exc_info=True)
            return False

    log.debug("Not connecting: %s is not callable (%r)", name, handler)
    return False


def safe_call(fn: Callable[..., T], *args: Any, parent=None, title: str = "Error", **kwargs: Any) -> Optional[T]:
    """Execute a function safely.

    - On exception: logs traceback and shows a user-friendly dialog.
    - Returns the function result, or None if it failed.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        log.error("Exception in callback %r", fn, exc_info=True)
        dialogs.error(title, f"{e}", details=str(e), parent=parent)
        return None
