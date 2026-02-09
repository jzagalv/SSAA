# -*- coding: utf-8 -*-
"""SSAA Designer - Boards helpers (non-UI core for the designer screen)."""

from __future__ import annotations

from typing import Dict, List

from PyQt5.QtCore import QPointF, Qt

from domain.ssaa_topology import TopoNode
from .graphics.items import _new_id


def _kind_from_tag(tag: str) -> str:
    t = (tag or "").strip().upper()
    for prefix in ("TGCA", "TDCA", "TGCC", "TDCC", "TDAF", "TDAyF"):
        if t.startswith(prefix):
            return prefix.replace("TDAF", "TDAyF")
    return "TGCA"


def iter_board_rows(scr):
    """Genera tableros/fuentes fisicos desde Instalaciones (gabinetes TD/TG)."""
    gabinetes = (getattr(scr.data_model, "gabinetes", None) or [])
    for gi, g in enumerate(gabinetes):
        if not bool(g.get("is_board", False)):
            continue
        tag = str(g.get("tag", "") or "").strip()
        if not tag:
            tag = str(g.get("nombre", "") or "").strip() or f"idx{gi}"
        desc = str(g.get("nombre", g.get("descripcion", "")) or "").strip()
        yield {
            "gi": gi,
            "gid": str(g.get("id", "") or ""),
            "tag": tag,
            "desc": desc,
        }


def refresh_boards_table(scr):
    if not hasattr(scr, "lst_boards"):
        return
    scr.lst_boards.clear()
    from PyQt5.QtWidgets import QListWidgetItem
    for row in iter_board_rows(scr):
        tag = row.get("tag", "")
        desc = row.get("desc", "")
        txt = (f"{tag}  —  {desc}").strip()
        it = QListWidgetItem(txt)
        it.setData(Qt.UserRole, row)
        scr.lst_boards.addItem(it)


def drop_board_on_canvas(scr, scene_pos: QPointF, board: Dict):
    """Crea un nodo TABLERO raíz al soltar desde Alimentación tableros (no consumible)."""
    if not board:
        return

    ws = getattr(scr, "_workspace", "CA_ES")
    tag = (board.get("tag") or "").strip()
    gid = (board.get("gid") or "").strip()
    base_key = gid or tag or f"idx{board.get('gi')}"
    board_key = f"board:{base_key}"
    node_id = f"{board_key}:{ws}"

    if node_id in getattr(scr, "_node_items", {}):
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(scr, "Tablero ya usado", "Este tablero ya está en esta capa.")
        return

    kind = _kind_from_tag(tag)

    node = TopoNode(
        id=node_id,
        kind=kind,
        name=(tag or base_key),
        pos=(float(scene_pos.x()), float(scene_pos.y())),
        dc_system="B1",
        p_w=0.0,
        meta={
            "tag": tag,
            "desc": (board.get("desc") or "").strip(),
            "layer": ws,
            "board_key": board_key,
            "gabinete_id": gid,
            "source": "board_feed_root",
            "root_board": True,
            "ports": [
                {"id": _new_id("p"), "name": "IN", "io": "IN", "side": "top", "x": 0.5},
                {"id": _new_id("p"), "name": "OUT", "io": "OUT", "side": "bottom", "x": 0.5},
            ],
        },
    )
    scr._add_node_item(node)
    scr._controller.after_topology_mutation(
        rebuild_edges=False,
        recompute_load_table=False,
        refresh_feeders=False,
        refresh_issues=True,
    )
