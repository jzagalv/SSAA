# -*- coding: utf-8 -*-
"""SSAA Designer - Feeders helpers (non-UI core for the designer screen).

This module centralizes the logic to:
- Build the list of available feeders/loads from DataModel.gabinetes
- Refresh the feeders list widget
- Handle drop of a feeder onto the canvas (create/consume load node)

It deliberately operates on a *screen-like* object passed as `scr` to avoid
circular imports with the screen module.
"""

from __future__ import annotations

from typing import Dict, List

from PyQt5.QtCore import QPointF, Qt

# Topology dataclasses live in domain (no Qt dependency)
from domain.ssaa_topology import TopoNode

# _new_id helper lives with graphics items (kept there to avoid duplication)
from .graphics.items import _new_id

def iter_feed_rows(scr):
    """Genera cargas disponibles desde la pestaña 'Alimentación tableros' (versión simplificada)."""
    gabinetes = (getattr(scr.data_model, "gabinetes", None) or [])
    for gi, g in enumerate(gabinetes):
        g_tag = str(g.get("tag", "") or "").strip()
        g_desc = str(g.get("nombre", g.get("descripcion", "")) or "").strip()

        yield {
            "scope": "gabinete",
            "gi": gi,
            "gid": str(g.get("id","") or ""),
            "ci": None,
            "tag": g_tag,
            "desc": g_desc,
            "cc_b1": bool(g.get("cc_b1", False)),
            "cc_b2": bool(g.get("cc_b2", False)),
            "ca_es": bool(g.get("ca_esencial", False)),
            "ca_noes": bool(g.get("ca_no_esencial", False)),
        }

        for ci, comp in enumerate(g.get("components", []) or []):
            # Aceptamos variaciones históricas/typos como "Induvidual" y
            # leemos tanto desde el dict raíz del componente como desde comp['data'].
            data = comp.get("data", {}) or {}
            alim_raw = (comp.get("alimentador") or data.get("alimentador") or "")
            alim_txt = str(alim_raw).strip().lower()
            if not (alim_txt == "individual" or alim_txt.startswith("indiv")):
                continue
            c_tag = str(comp.get("tag", comp.get("id", "")) or "").strip()
            # Descripción del componente: soporta variantes (en tu modelo muchas vienen en data)
            c_desc = (
                data.get("descripcion")
                or data.get("nombre")
                or data.get("name")
                or comp.get("descripcion")
                or comp.get("nombre")
                or comp.get("name")
                or ""
            )
            c_desc = str(c_desc).strip()
            # Si aún viene vacío, usa el tag del componente como identificador visible
            c_desc_visible = c_desc or c_tag or "(sin descripción)"
            # En Arquitectura SS/AA, mantenemos el TAG del tablero/gabinete.
            # La descripción se enriquece con el consumo individual para identificarlo.
            display_tag = g_tag  # TAG del tablero/gabinete
            display_desc = f"{g_desc} / {c_desc_visible}".strip(" /")

            # Flags del alimentador individual:
            # - Si ya fueron definidos desde 'Alimentación tableros', vienen en comp['data'][feed_*].
            # - Si aún no se han definido, inferimos a partir del tipo de consumo (C.C./C.A.)
            #   para que el alimentador aparezca igualmente en la lista.
            tipo = (
                data.get("tipo_consumo")
                or data.get("consumo")
                or comp.get("tipo_consumo")
                or comp.get("consumo")
                or ""
            )
            tt = str(tipo).strip().lower()
            infer = {"cc_b1": False, "cc_b2": False, "ca_es": False, "ca_noes": False}
            if tt:
                if tt.startswith("c.c") or tt.startswith("cc") or "c.c" in tt:
                    infer["cc_b1"] = True
                    infer["cc_b2"] = True
                elif "c.a" in tt or tt.startswith("ca"):
                    if "no" in tt and "esencial" in tt:
                        infer["ca_noes"] = True
                    elif "esencial" in tt:
                        infer["ca_es"] = True

            cc_b1 = bool(data.get("feed_cc_b1") or comp.get("feed_cc_b1") or infer["cc_b1"])
            cc_b2 = bool(data.get("feed_cc_b2") or comp.get("feed_cc_b2") or infer["cc_b2"])
            ca_es = bool(data.get("feed_ca_esencial") or comp.get("feed_ca_esencial") or infer["ca_es"])
            ca_noes = bool(data.get("feed_ca_no_esencial") or comp.get("feed_ca_no_esencial") or infer["ca_noes"])

            # Persistimos en el dict 'data' para que quede disponible en próximas vistas.
            data.setdefault("feed_cc_b1", cc_b1)
            data.setdefault("feed_cc_b2", cc_b2)
            data.setdefault("feed_ca_esencial", ca_es)
            data.setdefault("feed_ca_no_esencial", ca_noes)

            load_txt = (
                data.get("carga")
                or data.get("load")
                or data.get("detalle_carga")
                or comp.get("carga")
                or comp.get("load")
                or ""
            )
            load_txt = str(load_txt).strip()

            yield {
                "scope": "componente",
                "gi": gi,
                "gid": str(g.get("id","") or ""),
                "ci": ci,
                "tag": display_tag,
                "desc": display_desc,
                "cc_b1": cc_b1,
                "cc_b2": cc_b2,
                "ca_es": ca_es,
                "ca_noes": ca_noes,
                "load": load_txt,
            }
def refresh_feeders(scr):
    # "Actualizar" = recalcular pestañas disponibles y refrescar todo el workspace actual
    try:
        scr._rebuild_workspace_tabs()
        # Refrescar alimentadores (incluye consumos con alimentador 'Individual')
        scr._refresh_feeders_table()
        if hasattr(scr, "_refresh_sources_table"):
            scr._refresh_sources_table()
    except Exception:
        import logging
        logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
    # Recargar escena del workspace actual por si hubo cambios en las capas
    scr.reload_from_project()
    scr._refresh_feeders_table()
    if hasattr(scr, "_refresh_sources_table"):
        scr._refresh_sources_table()
    scr._refresh_issues_panel()

def refresh_feeders_table(scr):
    if not hasattr(scr, "lst_feeders"):
        return

    # Las pestañas (workspaces) se recalculan sólo al iniciar y cuando el usuario
    # presiona "Actualizar". Aquí sólo refrescamos la lista en el workspace actual.

    topo = scr._topo_store()
    used = set(topo.get("used_feeders", []) or [])

    ws = getattr(scr, "_workspace", "CA_ES")
    # Mapa workspace -> (circuit, dc_system, req_code)
    if ws == "CA_NOES":
        circuit, dc, req_code = "CA", "", "CA_NOES"
    elif ws == "CC_B1":
        circuit, dc, req_code = "CC", "B1", "CC_B1"
    elif ws == "CC_B2":
        circuit, dc, req_code = "CC", "B2", "CC_B2"
    else:
        circuit, dc, req_code = "CA", "", "CA_ES"

    feeders: List[Dict] = []
    for row in scr._iter_feed_rows():
        ok = False
        if req_code == "CA_ES":
            ok = bool(row.get("ca_es"))
        elif req_code == "CA_NOES":
            ok = bool(row.get("ca_noes"))
        elif req_code == "CC_B1":
            ok = bool(row.get("cc_b1"))
        elif req_code == "CC_B2":
            ok = bool(row.get("cc_b2"))

        if not ok:
            continue

        gid_for_key = row.get('gid') or row.get('gi')
        key = f"{row.get('scope')}:{gid_for_key}:{row.get('ci')}:{req_code}"
        if key in used:
            continue

        feeders.append({
            "key": key,
            "gabinete_id": row.get("gid") if row.get("scope") in ("gabinete","componente") else "",
            "tag": row.get("tag", ""),
            "desc": row.get("desc", ""),
            "load": row.get("load", ""),
            "circuit": circuit,
            "dc_system": (dc if circuit == "CC" else ""),
            "req": req_code,
            "source": "board_feed",
        })

    scr.lst_feeders.clear()
    from PyQt5.QtWidgets import QListWidgetItem
    for f in feeders:
        txt = (f"{f.get('tag','')}  —  {f.get('desc','')}".strip())
        it = QListWidgetItem(txt)
        it.setData(Qt.UserRole, f)
        scr.lst_feeders.addItem(it)

def drop_feeder_on_canvas(scr, scene_pos: QPointF, feeder: Dict):
    """Crea un nodo CARGA al soltar un alimentador en el canvas y lo consume."""
    if not feeder:
        return
    topo = scr._topo_store()
    used = set(topo.get("used_feeders", []) or [])
    key = feeder.get("key")
    if key:
        used.add(key)
        topo["used_feeders"] = sorted(used)

    tag = (feeder.get("tag") or "").strip()
    desc = (feeder.get("desc") or "").strip()
    circuit = (feeder.get("circuit") or "CA").upper()
    dc = (feeder.get("dc_system") or "B1").strip() or "B1"

    node = TopoNode(
        id=_new_id("CARGA"),
        kind="CARGA",
        name=tag,  # <- nombre corto (TAG)
        pos=(float(scene_pos.x()), float(scene_pos.y())),
        dc_system=(dc if circuit == "CC" else "B1"),
        p_w=0.0,
        meta={
            "tag": tag,
            "desc": desc,
            "load": (feeder.get("load") or "").strip(),  # <- NUEVO (si existe)
            "circuit": circuit,
            "dc_system": (dc if circuit == "CC" else ""),
            "feed_req": feeder.get("req"),
            "layer": feeder.get("req"),
            "feeder_key": key,
            "gabinete_id": feeder.get("gabinete_id") or "",
            "source": feeder.get("source", "board_feed"),
        },
    )
    scr._add_node_item(node)
    # Persist + refrescos (pipeline)
    scr._controller.pipeline.after_topology_mutation(
        rebuild_edges=False,
        recompute_load_table=False,
        refresh_feeders=True,
        refresh_issues=True,
    )
