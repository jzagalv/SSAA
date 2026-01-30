# -*- coding: utf-8 -*-
"""Items gráficos usados en la pantalla Cabinet/Consumos."""

from __future__ import annotations

from typing import Callable, Optional

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem

from .constants import GRID_SIZE, FONT_ITEM


class ComponentCardItem(QGraphicsItem):
    PADDING = 6
    HEADER_H = 22

    def __init__(
        self,
        comp_id: str,
        name: str,
        pos: QPointF,
        size,
        data: dict,
        on_move: Optional[Callable[[str, QPointF], None]] = None,
    ):
        super().__init__()
        self.comp_id = comp_id
        self.name = name
        self.w, self.h = size
        self.data = data or {}
        self._on_move = on_move

        self.setPos(pos)
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )

    def update_data(self, data: dict):
        self.data = data or {}
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.w, self.h)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            x = round(value.x() / GRID_SIZE) * GRID_SIZE
            y = round(value.y() / GRID_SIZE) * GRID_SIZE
            return QPointF(max(0, x), max(0, y))

        if change == QGraphicsItem.ItemPositionHasChanged and self._on_move:
            self._on_move(self.comp_id, self.pos())

        return super().itemChange(change, value)

    def paint(self, painter: QPainter, _option: QStyleOptionGraphicsItem, _widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        r = self.boundingRect()

        # borde según selección
        border_color = QColor(200, 0, 0) if self.isSelected() else QColor(0, 150, 0)

        painter.setPen(QPen(border_color, 2))
        painter.setBrush(QColor(250, 250, 250))
        painter.drawRoundedRect(r, 6, 6)

        # header
        header_rect = QRectF(0, 0, r.width(), self.HEADER_H)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(230, 240, 230))
        painter.drawRoundedRect(header_rect, 6, 6)

        painter.setPen(QPen(QColor(60, 60, 60), 1))
        painter.setFont(FONT_ITEM)
        painter.drawText(
            QRectF(self.PADDING, 0, r.width() - 2 * self.PADDING, self.HEADER_H),
            Qt.AlignLeft | Qt.AlignVCenter,
            self.name,
        )

        # cuerpo: TAG, tipo, fase, potencia
        tag = str(self.data.get("tag", ""))
        tipo = str(self.data.get("tipo_consumo", ""))
        fase = str(self.data.get("fase", ""))

        usar_va = bool(self.data.get("usar_va", False))
        if usar_va:
            pval = self.data.get("potencia_va", "")
            unit = "VA"
        else:
            pval = self.data.get("potencia_w", "")
            unit = "W"

        lines = []
        if tag:
            lines.append(f"TAG: {tag}")
        if tipo:
            lines.append(f"Tipo: {tipo}")
        # Solo CA muestra fase (si hay)
        if fase:
            lines.append(f"Fase: {fase}")
        if pval not in (None, ""):
            lines.append(f"P: {pval} {unit}")

        painter.setPen(QPen(QColor(40, 40, 40), 1))
        body_rect = QRectF(
            self.PADDING,
            self.HEADER_H + self.PADDING,
            self.w - 2 * self.PADDING - 8,
            self.h - self.HEADER_H - 2 * self.PADDING - 8,
        )
        painter.drawText(body_rect, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, "\n".join(lines))
