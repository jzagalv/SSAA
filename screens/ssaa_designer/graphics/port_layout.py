# -*- coding: utf-8 -*-
"""Deterministic port layout helpers for SSAA Designer."""

from __future__ import annotations

from typing import List

from PyQt5.QtCore import QRectF, QPointF

from .layout_constants import (
    CARD_WIDTH,
    CARD_GAP,
    SIDE_PADDING,
    SOURCE_CARD_WIDTH,
    BOARD_MIN_WIDTH,
)


def compute_node_width(kind: str, n_in: int, n_out: int) -> float:
    kind_u = (kind or "").upper()
    if kind_u in ("CARGA", "CARGADOR"):
        return CARD_WIDTH
    if kind_u == "FUENTE":
        return SOURCE_CARD_WIDTH
    if kind_u.startswith(("TG", "TD", "TDA")):
        slots = max(int(n_in or 0), int(n_out or 0), 1)
        width = slots * CARD_WIDTH + (slots - 1) * CARD_GAP + 2 * SIDE_PADDING
        return max(BOARD_MIN_WIDTH, float(width))
    return CARD_WIDTH


def compute_port_positions(rect: QRectF, n_ports: int, side: str) -> List[QPointF]:
    """Return positions for ports on top or bottom side of rect (absolute coordinates)."""
    n = int(n_ports or 0)
    if n <= 0:
        return []
    w = float(rect.width())
    h = float(rect.height())
    if n == 1:
        xs = [w / 2.0]
    else:
        pitch = CARD_WIDTH + CARD_GAP
        total = pitch * float(n - 1)
        if total > (w - 2.0 * SIDE_PADDING) and (n - 1) > 0:
            pitch = max((w - 2.0 * SIDE_PADDING) / float(n - 1), 1.0)
            total = pitch * float(n - 1)
        start = (w - total) / 2.0
        xs = [start + i * pitch for i in range(n)]
    y = 0.0 if (side or "").lower() == "top" else h
    return [QPointF(x, y) for x in xs]
