# -*- coding: utf-8 -*-
"""SSAA Designer - Sources helpers (non-UI core for the designer screen)."""

from __future__ import annotations

from typing import Dict, List

from PyQt5.QtCore import QPointF, Qt

from domain.ssaa_topology import TopoNode
from .graphics.items import _new_id


def iter_source_rows(scr):
    """Genera fuentes disponibles desde Instalaciones (gabinetes con is_energy_source)."""
    gabinetes = (getattr(scr.data_model, "gabinetes", None) or [])
    for gi, g in enumerate(gabinetes):
        if not bool(g.get("is_energy_source", False)):
            continue
        g_tag = str(g.get("tag", "") or "").strip()
        g_desc = str(g.get("nombre", g.get("descripcion", "")) or "").strip()
        yield {
            "gi": gi,
            "gid": str(g.get("id", "") or ""),
            "tag": g_tag,
            "desc": g_desc,
        }


def refresh_sources_table(scr):
    if not hasattr(scr, "lst_sources"):
        return
    scr.lst_sources.clear()
    from PyQt5.QtWidgets import QListWidgetItem
    for row in iter_source_rows(scr):
        tag = row.get("tag", "")
        desc = row.get("desc", "")
        txt = (f"{tag}  —  {desc}").strip()
        it = QListWidgetItem(txt)
        it.setData(Qt.UserRole, row)
        scr.lst_sources.addItem(it)


def drop_source_on_canvas(scr, scene_pos: QPointF, source: Dict):
    """Crea un nodo FUENTE al soltar una fuente en el canvas (no consumible)."""
    if not source:
        return

    ws = getattr(scr, "_workspace", "CA_ES")
    tag = (source.get("tag") or "").strip()
    gid = (source.get("gid") or "").strip()
    gi = source.get("gi")
    base_key = gid or tag or f"idx{gi}"
    source_key = f"src:{base_key}"
    node_id = f"{source_key}:{ws}"

    if node_id in getattr(scr, "_node_items", {}):
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(scr, "Fuente ya usada", "Esta fuente ya está en esta capa.")
        return

    node = TopoNode(
        id=node_id,
        kind="FUENTE",
        name=(tag or base_key),
        pos=(float(scene_pos.x()), float(scene_pos.y())),
        dc_system="B1",
        p_w=0.0,
        meta={
            "tag": tag,
            "desc": (source.get("desc") or "").strip(),
            "layer": ws,
            "source_key": source_key,
            "gabinete_id": gid,
            "source": "energy_source",
            "ports": [
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
