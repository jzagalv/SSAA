# -*- coding: utf-8 -*-
"""screens/base.py

Base class for UI screens.

Goal:
- Provide a single, consistent place to store the DataModel reference
- Offer optional hooks (load_from_model/save_to_model/refresh)
- Keep changes low-risk: screens can adopt this gradually
"""

from __future__ import annotations

from contextlib import contextmanager

from PyQt5.QtWidgets import QWidget, QUndoStack

try:
    from ui.common.state import get_int
except Exception:
    def get_int(_key: str, default: int = 10) -> int:
        return int(default)

try:
    from ui.common.ui_state_binder import UiStateBinder
except Exception:
    UiStateBinder = None


class ScreenBase(QWidget):
    """Common base for screens that interact with DataModel.

    This class is intentionally lightweight. Screens may override:
    - load_from_model(): populate UI from model
    - save_to_model(): push UI changes into model (if applicable)
    - refresh(): default calls load_from_model()
    """

    def __init__(self, data_model, parent=None):
        super().__init__(parent)
        if __debug__:
            assert data_model is not None, "ScreenBase requires a data_model instance"
        self.data_model = data_model
        self.undo_stack = QUndoStack(self)
        try:
            self.undo_stack.setUndoLimit(get_int("ui/undo_limit", 10))
        except Exception:
            self.undo_stack.setUndoLimit(10)
        self._ui_state = None
        self._last_seen_revision = None

    def load_from_model(self) -> None:
        pass

    def save_to_model(self) -> None:
        pass

    def refresh(self) -> None:
        self.load_from_model()

    def refresh_from_model(self, reason: str = "", force: bool = False) -> None:
        _ = reason
        dm = self.data_model
        try:
            rev = int(getattr(dm, "revision", 0))
        except Exception:
            rev = 0
        if not force and self._last_seen_revision == rev:
            return
        try:
            with self.ui_refresh_scope():
                reload_fn = getattr(self, "reload_from_project", None)
                if callable(reload_fn):
                    reload_fn()
                else:
                    refresh_fn = getattr(self, "refresh", None)
                    if callable(refresh_fn):
                        refresh_fn()
        finally:
            self._last_seen_revision = rev

    def on_view_activated(self, reason: str = "") -> None:
        try:
            self.refresh_from_model(reason=reason, force=False)
        except TypeError:
            # Compatibilidad con pantallas legacy que no aceptan kwargs.
            self.refresh_from_model()

    def set_dirty(self, flag: bool = True) -> None:
        # Compatibilidad: DataModel moderno usa mark_dirty(bool)
        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(bool(flag))
        elif hasattr(self.data_model, "set_dirty"):
            self.data_model.set_dirty(bool(flag))

    def mark_dirty(self) -> None:
        """Convenience alias: mark the project as dirty."""
        self.set_dirty(True)

    @contextmanager
    def ui_refresh_scope(self):
        dm = self.data_model
        prev = bool(getattr(dm, "_ui_refreshing", False))
        try:
            if hasattr(dm, "set_ui_refreshing"):
                dm.set_ui_refreshing(True)
            yield
        finally:
            if hasattr(dm, "set_ui_refreshing"):
                dm.set_ui_refreshing(prev)

    def apply_undo_limit(self, limit: int) -> None:
        try:
            self.undo_stack.setUndoLimit(int(limit))
        except Exception:
            pass

    def init_ui_state(self):
        if self._ui_state is None and UiStateBinder is not None:
            try:
                self._ui_state = UiStateBinder()
            except Exception:
                self._ui_state = None
        return self._ui_state

    def _restore_ui_state(self) -> None:
        try:
            if self._ui_state is not None:
                self._ui_state.restore()
        except Exception:
            pass

    def _persist_ui_state(self) -> None:
        try:
            if self._ui_state is not None:
                self._ui_state.persist()
        except Exception:
            pass

    def can_deactivate(self, parent=None) -> bool:
        return True

    def can_close(self, parent=None) -> bool:
        return self.can_deactivate(parent)

    def wire_model_signals(self) -> None:
        """Optional hook for screens that subscribe to model signals.

        Default: no-op.
        """
        return
