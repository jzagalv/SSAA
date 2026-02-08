# -*- coding: utf-8 -*-
"""BoardListWidget for SSAA Designer.

UI-only widget that enables drag&drop of board dict payloads.
"""

from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QListWidget


class BoardListWidget(QListWidget):
    """Lista de tableros/fuentes disponibles con drag&drop."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setDragEnabled(True)

    def startDrag(self, supportedActions):
        items = self.selectedItems()
        if not items:
            return
        it = items[0]
        board = it.data(Qt.UserRole)
        if not board:
            return
        try:
            import json as _json
            payload = _json.dumps(board, ensure_ascii=False)
        except Exception:
            return
        md = QMimeData()
        md.setData("application/x-ssaa-board", payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(md)
        drag.exec_(Qt.CopyAction)
