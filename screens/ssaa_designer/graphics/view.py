# -*- coding: utf-8 -*-
"""QGraphicsView implementation for SSAA Designer."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene

class TopoView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, on_delete_selected=None, on_drop_feeder=None, on_drop_source=None, on_drop_board=None):
        super().__init__(scene)
        self._on_delete_selected = on_delete_selected
        self._on_drop_feeder = on_drop_feeder
        self._on_drop_source = on_drop_source
        self._on_drop_board = on_drop_board
        self.setAcceptDrops(True)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        # AutoCAD-like navigation
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self._panning = False
        self._pan_start = None



    def wheelEvent(self, event):
        # Zoom in/out with mouse wheel (CAD-like)
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.2 if delta > 0 else 1/1.2
        self.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event):
        # Middle button pan
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-ssaa-feeder") or event.mimeData().hasFormat("application/x-ssaa-source") or event.mimeData().hasFormat("application/x-ssaa-board"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-ssaa-feeder") or event.mimeData().hasFormat("application/x-ssaa-source") or event.mimeData().hasFormat("application/x-ssaa-board"):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-ssaa-feeder") and self._on_drop_feeder:
            try:
                raw = bytes(event.mimeData().data("application/x-ssaa-feeder")).decode("utf-8")
                import json as _json
                feeder = _json.loads(raw)
            except Exception:
                feeder = None
            if feeder:
                pos = self.mapToScene(event.pos())
                self._on_drop_feeder(pos, feeder)
                event.acceptProposedAction()
                return
        if event.mimeData().hasFormat("application/x-ssaa-source") and self._on_drop_source:
            try:
                raw = bytes(event.mimeData().data("application/x-ssaa-source")).decode("utf-8")
                import json as _json
                source = _json.loads(raw)
            except Exception:
                source = None
            if source:
                pos = self.mapToScene(event.pos())
                self._on_drop_source(pos, source)
                event.acceptProposedAction()
                return
        if event.mimeData().hasFormat("application/x-ssaa-board") and hasattr(self, "_on_drop_board") and self._on_drop_board:
            try:
                raw = bytes(event.mimeData().data("application/x-ssaa-board")).decode("utf-8")
                import json as _json
                board = _json.loads(raw)
            except Exception:
                board = None
            if board:
                pos = self.mapToScene(event.pos())
                self._on_drop_board(pos, board)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self._on_delete_selected:
                self._on_delete_selected()
                e.accept()
                return
        super().keyPressEvent(e)
