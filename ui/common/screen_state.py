from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def restore_screen_state(screen: Any) -> None:
    if screen is None:
        return
    try:
        for name in ("restore_ui_state", "_restore_ui_state", "restore_state"):
            fn = getattr(screen, name, None)
            if callable(fn):
                fn()
                return
    except Exception:
        log.debug("restore_screen_state failed (best-effort).", exc_info=True)


def persist_screen_state(screen: Any) -> None:
    if screen is None:
        return
    try:
        for name in ("persist_ui_state", "_persist_ui_state", "persist_state"):
            fn = getattr(screen, name, None)
            if callable(fn):
                fn()
                return
    except Exception:
        log.debug("persist_screen_state failed (best-effort).", exc_info=True)


def iter_main_screens(app_widget: Any) -> list[Any]:
    screens: list[Any] = []
    if app_widget is None:
        return screens
    try:
        count = int(app_widget.count())
    except Exception:
        return screens
    for i in range(count):
        try:
            w = app_widget.widget(i)
            if w is not None:
                screens.append(w)
        except Exception:
            continue
    return screens
