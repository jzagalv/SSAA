# -*- coding: utf-8 -*-
"""QGraphicsView con rejilla y soporte drag & drop para Cabinet/Consumos."""

from __future__ import annotations

import json

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtWidgets import QGraphicsView, QMenu

from .constants import COLOR_GRID_LIGHT, GRID_SIZE
from .items import ComponentCardItem

# Mime para drag & drop enriquecido (name + lib_uid + code)
MIME_CONSUMO = "application/x-ssaa-consumo"


class CustomGraphicsView(QGraphicsView):
    """Vista con rejilla y drop para crear componentes en el gabinete."""

    def __init__(self, scene, parent_screen, parent=None):
        super().__init__(scene, parent)
        self.parent_screen = parent_screen
        self.setRenderHint(QPainter.Antialiasing)
        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.RubberBandDrag)

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.fillRect(rect, Qt.white)

        left = int(rect.left()) - (int(rect.left()) % GRID_SIZE)
        top = int(rect.top()) - (int(rect.top()) % GRID_SIZE)
        right = int(rect.right())
        bottom = int(rect.bottom())

        painter.setPen(QPen(COLOR_GRID_LIGHT, 1))

        x = left
        while x <= right:
            painter.drawLine(int(x), int(top), int(x), int(bottom))
            x += GRID_SIZE

        y = top
        while y <= bottom:
            painter.drawLine(int(left), int(y), int(right), int(y))
            y += GRID_SIZE

    # drag & drop
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not (event.mimeData().hasText() or event.mimeData().hasFormat(MIME_CONSUMO)):
            event.ignore()
            return

        # Soporte: drag clásico (texto) y drag enriquecido (JSON con lib_uid)
        name = event.mimeData().text()
        lib_uid = ""
        code = ""
        if event.mimeData().hasFormat(MIME_CONSUMO):
            try:
                raw = bytes(event.mimeData().data(MIME_CONSUMO)).decode("utf-8")
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    name = str(payload.get("name", name) or name)
                    lib_uid = str(payload.get("lib_uid", "") or "")
                    code = str(payload.get("code", "") or "")
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        pos_view = event.pos()
        pos_scene = self.mapToScene(pos_view)
        x = round(pos_scene.x() / GRID_SIZE) * GRID_SIZE
        y = round(pos_scene.y() / GRID_SIZE) * GRID_SIZE

        self.parent_screen.add_component_at(
            name,
            QPointF(max(0, x), max(0, y)),
            lib_uid=lib_uid,
            code=code,
        )
        event.acceptProposedAction()

    def contextMenuEvent(self, event):
        # menú contextual para borrar tarjetas seleccionadas
        selected_cards = [it for it in self.scene().selectedItems() if isinstance(it, ComponentCardItem)]
        if not selected_cards:
            return super().contextMenuEvent(event)

        menu = QMenu(self)
        act_delete = menu.addAction("Eliminar componente(s)")
        chosen = menu.exec_(self.mapToGlobal(event.pos()))
        if chosen == act_delete:
            for card in selected_cards:
                self.parent_screen.remove_component_item(card)
