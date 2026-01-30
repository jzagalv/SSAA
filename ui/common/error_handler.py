# -*- coding: utf-8 -*-
"""UI error handling helpers.

Wrap UI callbacks to avoid repeating try/except + QMessageBox everywhere.

This module logs full tracebacks and shows a user-friendly error dialog.
"""

from __future__ import annotations

import logging
import traceback
from typing import Callable, Optional, TypeVar

from PyQt5.QtWidgets import QWidget

from ui.common import dialogs

T = TypeVar("T")


def run_guarded(
    fn: Callable[[], T],
    *,
    parent: Optional[QWidget] = None,
    title: str = "Error",
    user_message: str = "Ocurrió un error.",
    logger_name: str = "ssaa",
) -> Optional[T]:
    """Run a callable and handle any exception.

    Returns the callable result, or None if an exception occurred.
    """
    try:
        return fn()
    except Exception as e:
        tb = traceback.format_exc()
        logging.getLogger(logger_name).exception("Unhandled UI exception: %s", e)
        dialogs.error(parent, title, user_message, details=tb)
        return None
