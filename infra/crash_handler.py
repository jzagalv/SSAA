# -*- coding: utf-8 -*-
"""Global crash/exception handlers.

Goal:
- capture unexpected exceptions in a log file (user space)
- avoid silent exits
- keep UI-level wrappers optional (ui/common/error_handler.py)

This module is safe to import before QApplication is created.
"""

from __future__ import annotations

import logging
import sys
import threading
import traceback
from types import TracebackType
from typing import Optional, Type


def _log_exception(exc_type: Type[BaseException], exc: BaseException, tb: Optional[TracebackType]) -> None:
    try:
        logging.getLogger(__name__).critical(
            "Unhandled exception: %s",
            "".join(traceback.format_exception(exc_type, exc, tb)),
        )
    except Exception:
        # last resort
        try:
            sys.stderr.write("Unhandled exception (logging failed):\n")
            sys.stderr.write("".join(traceback.format_exception(exc_type, exc, tb)))
        except Exception:
            pass


def install_global_exception_handlers() -> None:
    """Install sys/thread exception hooks to ensure crashes are logged."""
    sys.excepthook = _log_exception  # type: ignore[assignment]

    # Python 3.8+: thread exceptions
    if hasattr(threading, "excepthook"):
        def _thread_hook(args):  # pragma: no cover
            _log_exception(args.exc_type, args.exc_value, args.exc_traceback)

        threading.excepthook = _thread_hook  # type: ignore[assignment]
