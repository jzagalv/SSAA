from __future__ import annotations

from typing import Any, Callable

from PyQt5.QtWidgets import QUndoCommand


class ApplyValueCommand(QUndoCommand):
    def __init__(
        self,
        text: str,
        apply_fn: Callable[[Any], None],
        old_value: Any,
        new_value: Any,
    ) -> None:
        super().__init__(str(text or "Change value"))
        self._apply_fn = apply_fn
        self._old_value = old_value
        self._new_value = new_value

    def undo(self) -> None:
        self._apply_fn(self._old_value)

    def redo(self) -> None:
        self._apply_fn(self._new_value)
