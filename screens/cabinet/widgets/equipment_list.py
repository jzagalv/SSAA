# -*- coding: utf-8 -*-
"""Lista de equipos arrastrables para la pantalla Cabinet/Consumos."""

from __future__ import annotations

import json

from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QListWidget

from ..graphics.view import MIME_CONSUMO


class EquipmentListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item:
            return

        drag = QDrag(self)
        mime = QMimeData()

        # Texto visible (nombre). Además, si proviene de librería, incluimos lib_uid/code.
        name = item.text()
        mime.setText(name)

        lib_uid = item.data(Qt.UserRole)
        code = item.data(Qt.UserRole + 1)
        payload = {"name": name, "lib_uid": lib_uid or "", "code": code or ""}
        try:
            mime.setData(MIME_CONSUMO, json.dumps(payload).encode("utf-8"))
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        drag.setMimeData(mime)
        drag.exec_(supportedActions)
