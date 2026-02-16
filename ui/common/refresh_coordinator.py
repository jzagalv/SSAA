# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

log = logging.getLogger(__name__)


class RefreshCoordinator(QObject):
    refresh_started = pyqtSignal(str)
    refresh_finished = pyqtSignal(str)

    def __init__(self, data_model, screens_provider):
        super().__init__()
        self._dm = data_model
        self._screens_provider = screens_provider
        self._pending = False
        self._pending_reason = ""
        self._pending_force = False

    def request(self, reason: str, force: bool = False) -> None:
        self._pending_reason = str(reason or self._pending_reason or "refresh")
        self._pending_force = bool(self._pending_force or force)
        if self._pending:
            return
        self._pending = True
        QTimer.singleShot(0, self._process)

    def refresh_active_only(self, active_screen, reason: str) -> None:
        if active_screen is None:
            return
        try:
            hook = getattr(active_screen, "on_view_activated", None)
            if callable(hook):
                hook(reason=str(reason or "tab_changed"))
                return
        except Exception:
            log.debug("active-only hook failed", exc_info=True)
        try:
            hook = getattr(active_screen, "refresh_from_model", None)
            if callable(hook):
                try:
                    hook(reason=str(reason or "tab_changed"), force=False)
                except TypeError:
                    hook()
        except Exception:
            log.debug("active-only refresh fallback failed", exc_info=True)

    def _process(self) -> None:
        reason = str(self._pending_reason or "refresh")
        force = bool(self._pending_force)
        self._pending = False
        self._pending_reason = ""
        self._pending_force = False

        self.refresh_started.emit(reason)
        dm = self._dm
        prev = bool(getattr(dm, "_ui_refreshing", False))
        try:
            if hasattr(dm, "set_ui_refreshing"):
                dm.set_ui_refreshing(True)
            else:
                setattr(dm, "_ui_refreshing", True)

            screens = []
            try:
                screens = list(self._screens_provider() or [])
            except Exception:
                screens = []

            for screen in screens:
                if screen is None:
                    continue
                try:
                    fn = getattr(screen, "refresh_from_model", None)
                    if callable(fn):
                        try:
                            fn(reason=reason, force=force)
                        except TypeError:
                            fn()
                except Exception:
                    log.debug("screen refresh failed (best-effort)", exc_info=True)
        finally:
            try:
                if hasattr(dm, "set_ui_refreshing"):
                    dm.set_ui_refreshing(prev)
                else:
                    setattr(dm, "_ui_refreshing", prev)
            finally:
                self.refresh_finished.emit(reason)

