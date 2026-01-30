# -*- coding: utf-8 -*-
"""screens/base.py

Base class for UI screens.

Goal:
- Provide a single, consistent place to store the DataModel reference
- Offer optional hooks (load_from_model/save_to_model/refresh)
- Keep changes low-risk: screens can adopt this gradually
"""

from __future__ import annotations

from PyQt5.QtWidgets import QWidget


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

    def load_from_model(self) -> None:
        pass

    def save_to_model(self) -> None:
        pass

    def refresh(self) -> None:
        self.load_from_model()

    def set_dirty(self, flag: bool = True) -> None:
        # Keep compatibility with existing DataModel API
        if hasattr(self.data_model, "set_dirty"):
            self.data_model.set_dirty(flag)

    def mark_dirty(self) -> None:
        """Convenience alias: mark the project as dirty."""
        self.set_dirty(True)

    def wire_model_signals(self) -> None:
        """Optional hook for screens that subscribe to model signals.

        Default: no-op.
        """
        return
