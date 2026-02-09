# -*- coding: utf-8 -*-
"""Auto layout helpers for SSAA Designer (ports -> child placement)."""

from __future__ import annotations

from typing import Dict, List

from PyQt5.QtCore import QPointF

from .layout_constants import CARD_WIDTH, CARD_GAP, SIDE_PADDING, VERT_SPACING, STACK_SPACING


def build_slot_centers(board_item) -> List[float]:
    """Return slot center x positions (scene coords) for OUT ports."""
    ports = (board_item.node.meta or {}).get("ports", []) or []
    out_ports = [p for p in ports if (p.get("io") or "").upper() == "OUT"]
    n = max(len(out_ports), 1)
    board_left = board_item.pos().x()
    centers = []
    for i in range(n):
        cx = board_left + SIDE_PADDING + i * (CARD_WIDTH + CARD_GAP) + (CARD_WIDTH / 2.0)
        centers.append(cx)
    return centers


def auto_place_children(board_item, edges, node_items: Dict[str, object], only_unpinned: bool = True) -> None:
    """Place children under board OUT slots. Respects manual_pos."""
    ports = (board_item.node.meta or {}).get("ports", []) or []
    out_ports = [p for p in ports if (p.get("io") or "").upper() == "OUT"]
    out_port_ids = [str(p.get("id") or "") for p in out_ports]
    slot_centers = build_slot_centers(board_item)

    # group by slot index
    slot_children: Dict[int, List[object]] = {}
    for e in edges:
        if e.src != board_item.node.id:
            continue
        dst_item = node_items.get(e.dst)
        if dst_item is None:
            continue
        if only_unpinned and ((dst_item.node.meta or {}).get("ui", {}).get("manual_pos") is True):
            continue
        out_id = (e.meta or {}).get("out_port_id") or (e.meta or {}).get("src_port")
        out_id = str(out_id or "")
        try:
            idx = out_port_ids.index(out_id)
        except Exception:
            idx = 0
        slot_children.setdefault(idx, []).append(dst_item)

    board_bottom = board_item.pos().y() + board_item.node.size[1]

    for idx, children in slot_children.items():
        cx = slot_centers[min(idx, len(slot_centers) - 1)]
        for k, child in enumerate(children):
            ch = float(child.node.size[1])
            x = cx - (float(child.node.size[0]) / 2.0)
            y = board_bottom + VERT_SPACING + k * (ch + STACK_SPACING)
            child.setPos(QPointF(x, y))
            child.node.pos = (float(x), float(y))
