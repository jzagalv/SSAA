# -*- coding: utf-8 -*-
"""FeedListWidget extracted from ssaa_designer_screen.

UI-only widget that enables drag&drop of feeder dict payloads.
"""

from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QListWidget


class FeedListWidget(QListWidget):
    """Lista de alimentadores disponibles (Tag + Descripción) con drag&drop."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setDragEnabled(True)

    def startDrag(self, supportedActions):
        items = self.selectedItems()
        if not items:
            return
        it = items[0]
        feeder = it.data(Qt.UserRole)
        if not feeder:
            return
        try:
            import json as _json
            payload = _json.dumps(feeder, ensure_ascii=False)
        except Exception:
            return
        md = QMimeData()
        md.setData("application/x-ssaa-feeder", payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(md)
        drag.exec_(Qt.CopyAction)
