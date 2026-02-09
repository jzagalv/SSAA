# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QFrame, QToolButton, QVBoxLayout


class Sidebar(QFrame):
    navigate_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self._active_index = -1
        self._collapsed = False
        self._buttons = {}
        self._labels = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._collapse_btn = QToolButton(self)
        self._collapse_btn.setObjectName("SidebarItem")
        self._collapse_btn.setText("Ocultar")
        self._collapse_btn.clicked.connect(self._toggle_collapsed)
        layout.addWidget(self._collapse_btn)

        items = [
            (0, "Proyecto"),
            (1, "Instalaciones"),
            (2, "Consumos (gabinetes)"),
            (3, "Consumos C.C."),
            (4, "Banco y cargador"),
            (5, "Alimentacion tableros"),
            (6, "Arquitectura SS/AA"),
            (7, "Cuadros de carga"),
        ]
        for idx, label in items:
            btn = QToolButton(self)
            btn.setObjectName("SidebarItem")
            btn.setText(label)
            btn.clicked.connect(lambda _=False, i=idx: self.navigate_requested.emit(i))
            layout.addWidget(btn)
            self._buttons[idx] = btn
            self._labels[idx] = label

        layout.addStretch(1)
        self.setMinimumWidth(220)
        self.setMaximumWidth(220)

    def _toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_active(self, index: int) -> None:
        self._active_index = int(index)
        for idx, btn in self._buttons.items():
            active = idx == self._active_index
            btn.setProperty("active", active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = bool(collapsed)
        if self._collapsed:
            self.setMinimumWidth(56)
            self.setMaximumWidth(56)
            self._collapse_btn.setText(">")
            for idx, btn in self._buttons.items():
                txt = self._labels.get(idx, "")
                btn.setText(txt[:1] if txt else "")
                btn.setToolTip(txt)
        else:
            self.setMinimumWidth(220)
            self.setMaximumWidth(220)
            self._collapse_btn.setText("Ocultar")
            for idx, btn in self._buttons.items():
                txt = self._labels.get(idx, "")
                btn.setText(txt)
                btn.setToolTip("")
