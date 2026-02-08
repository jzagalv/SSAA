# -*- coding: utf-8 -*-
"""Context and connection actions for SSAA Designer.

This module hosts UI-driven actions that were previously implemented inline in
ssaa_designer_screen.py (connect from context, auto-connect orphans, etc.).
Keeping them here reduces the size of the screen module and prevents future
refactors from mixing UI/menu logic with scene/model logic.
"""

from __future__ import annotations

from typing import Dict, List

from PyQt5.QtWidgets import QMessageBox, QInputDialog

from domain.ssaa_topology import TopoEdge

from .graphics.items import _new_id


def connect_nodes_checked(scr, circuit: str, dc: str, src: str, dst: str) -> bool:
    if not src or not dst:
        return False
    if src == dst:
        QMessageBox.warning(scr, "Conexión", "No se puede conectar un nodo consigo mismo.")
        return False

    # duplicado
    for it in scr._edge_items.values():
        e = it.edge
        if e.src == src and e.dst == dst and (e.circuit or "CA").upper() == circuit.upper():
            if circuit.upper() != "CC" or (e.dc_system or "B1") == (dc or "B1"):
                return False

    if scr._would_create_cycle(circuit, dc, src, dst):
        QMessageBox.warning(scr, "Conexión", "Esa conexión generaría un ciclo. Se canceló.")
        return False

    edge = TopoEdge(
        id=_new_id("E"),
        src=src,
        dst=dst,
        circuit=circuit.upper(),
        dc_system=(dc or "B1") if circuit.upper() == "CC" else "",
        meta={},
    )
    scr._add_edge_item(edge)
    scr._persist()
    scr._rebuild_all_edges()
    scr._compute_load_table_rows()
    scr._refresh_issues_panel()
    return True
def auto_connect_orphans_interactive(scr):
    scr._refresh_issues_panel()
    layer = scr._selected_issue_layer()
    circuit = layer["circuit"]
    dc = layer["dc"]

    issues = scr._last_layer_issues or []
    orphans = [i for i in issues if i.get("code") == "NODE_ORPHAN" and i.get("node_id")]

    if not orphans:
        QMessageBox.information(scr, "Auto-conectar", "No hay cargas huérfanas en esta capa.")
        return

    for it in orphans:
        nid = it.get("node_id")
        sugg = scr._suggest_feeder_for_node(nid, circuit, dc)
        node_name = scr._node_items[nid].node.name if nid in scr._node_items else nid

        if not sugg:
            QMessageBox.information(scr, "Auto-conectar", f"No hay candidatos para alimentar '{node_name}'.")
            continue

        feeder_name = scr._node_items[sugg].node.name if sugg in scr._node_items else sugg

        mb = QMessageBox(scr)
        mb.setIcon(QMessageBox.Question)
        mb.setWindowTitle("Auto-conectar huérfano")
        mb.setText(f"Conectar '{node_name}' desde '{feeder_name}'?\n(Capa: {circuit}{' '+dc if circuit=='CC' else ''})")
        yes = mb.addButton("Sí", QMessageBox.AcceptRole)
        no = mb.addButton("No", QMessageBox.RejectRole)
        cancel = mb.addButton("Cancelar", QMessageBox.DestructiveRole)
        mb.exec_()

        clicked = mb.clickedButton()
        if clicked == cancel:
            break
        if clicked == no:
            continue

        connect_nodes_checked(circuit, dc, sugg, nid)
def connect_from_context(scr, dst_node_id: str):
    """Acción asistida desde menú contextual: el usuario elige el nodo alimentador."""
    layer = scr._selected_issue_layer()
    circuit = layer["circuit"]
    dc = layer["dc"]

    items = []
    ids = []
    for nid, it in scr._node_items.items():
        if nid == dst_node_id:
            continue
        k = (it.node.kind or "").upper()
        if k in ("CARGA", "CARGADOR"):
            continue
        if circuit.upper() == "CC" and (it.node.dc_system or "B1") != (dc or "B1"):
            continue
        items.append(it.node.name)
        ids.append(nid)

    if not items:
        QMessageBox.information(scr, "Conectar", "No hay nodos de carga disponibles en esta capa.")
        return

    name, ok = QInputDialog.getItem(scr, "Conectar desde…", "Selecciona alimentador:", items, 0, False)
    if not ok:
        return
    src_id = ids[items.index(name)]
    connect_nodes_checked(circuit, dc, src_id, dst_node_id)

# ---------------- validation / load table ----------------
