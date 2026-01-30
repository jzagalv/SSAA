# -*- coding: utf-8 -*-
"""SSAA Designer persistence helpers.

Esta capa maneja exclusivamente lectura/escritura al DataModel (proyecto)
relacionada con la topología del diseñador SS/AA.

Objetivo:
- Evitar que el controller y/o el screen mezclen UI con I/O.
- Centralizar compatibilidad/migración de formatos de topología.
"""

from __future__ import annotations

from typing import Dict, Any

from domain.project_facade import ProjectFacade
from core.keys import ProjectKeys as K


class SSaaDesignerPersistence:
    def __init__(self, screen):
        self.screen = screen

    def topo_store(self) -> Dict:
        """Devuelve el store de topología para el workspace actual.

        Persistencia:
            proyecto['ssaa_topology_layers'][<workspace>] = {
                'nodes': [], 'edges': [], 'used_feeders': []
            }

        Compatibilidad:
            - Si existe proyecto[K.SSAA_TOPOLOGY] antiguo, se migra a 'CA_ES' la primera vez.
        """
        scr = self.screen
        p = getattr(scr.data_model, "proyecto", {}) or {}
        pf = ProjectFacade(p)

        # migración best-effort desde formato antiguo (K.SSAA_TOPOLOGY -> layers['CA_ES'])
        old = pf.get_ssaa_topology_legacy()
        if isinstance(old, dict) and old.get("nodes") is not None and old.get("edges") is not None:
            layers = pf.ensure_dict(K.SSAA_TOPOLOGY_LAYERS)
            layers.setdefault("CA_ES", old)
            # no borramos K.SSAA_TOPOLOGY para no romper otras partes

        ws = getattr(scr, "_workspace", "CA_ES") or "CA_ES"
        return pf.ensure_ssaa_topology_layer(ws)

    def persist(self) -> None:
        """Persistir nodos/aristas actuales desde items Qt hacia el proyecto."""
        scr = self.screen
        topo = self.topo_store()
        topo["nodes"] = [it.node.to_dict() for it in scr._node_items.values()]
        topo["edges"] = [it.edge.to_dict() for it in scr._edge_items.values()]

        if hasattr(scr.data_model, "mark_dirty"):
            scr.data_model.mark_dirty(True)
