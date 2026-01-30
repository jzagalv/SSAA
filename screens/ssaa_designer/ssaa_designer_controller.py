# -*- coding: utf-8 -*-
"""SSAA Designer Controller (screens/ssaa_designer)

Este módulo centraliza dos responsabilidades que estaban dentro del screen:

1) Persistencia de topología por workspace dentro del DataModel (proyecto).
2) Refresco del panel de issues (cálculo + presentación en QListWidget).

La idea es mantener a ``ssaa_designer_screen.py`` como UI (Qt) y eventos
gráficos, mientras este controller orquesta y escribe al modelo.
"""

from __future__ import annotations

import logging
from typing import Dict, List

from app.base_controller import BaseController
from core.sections import Section
from domain.project_facade import ProjectFacade

from .widgets.issues_presenter import IssuesPresenter
from .persistence import SSaaDesignerPersistence
from .update_pipeline import SSaaDesignerUpdatePipeline


log = logging.getLogger(__name__)


class SSaaDesignerController(BaseController):
    def __init__(self, screen):
        super().__init__(screen=screen, section=Section.DESIGNER)
        self.screen = screen
        self.persistence = SSaaDesignerPersistence(screen)
        self.issues_presenter = IssuesPresenter(screen)
        self.pipeline = SSaaDesignerUpdatePipeline(screen=screen, controller=self)

    # ---------------- storage ----------------
    def topo_store(self) -> Dict:
        """Delegación a persistencia (compatibilidad)."""
        return self.persistence.topo_store()

    def persist(self) -> None:
        """Delegación a persistencia (compatibilidad)."""
        return self.persistence.persist()

    # ---------------- issues ----------------
    
    def after_topology_mutation(
        self,
        *,
        rebuild_edges: bool = True,
        recompute_load_table: bool = False,
        refresh_feeders: bool = False,
        refresh_issues: bool = True,
    ) -> None:
        """Orquesta refrescos posteriores a un cambio de topología.

        Envuelve el pipeline interno para que el screen no acceda a detalles de orquestación.
        """
        self.pipeline.after_topology_mutation(
            rebuild_edges=rebuild_edges,
            recompute_load_table=recompute_load_table,
            refresh_feeders=refresh_feeders,
            refresh_issues=refresh_issues,
        )

    def refresh_issues_panel(self) -> None:
        """Recalcula issues (reglas) y delega el pintado al presenter UI."""
        scr = self.screen
        if not hasattr(scr, "lst_issues"):
            return

        layer = scr._selected_issue_layer()
        circuit = layer["circuit"]
        dc = layer["dc"]

        nodes = [it.node for it in scr._node_items.values()]
        edges = [it.edge for it in scr._edge_items.values()]
        issues: List[Dict] = scr._validate_rules_layered(nodes, edges, circuit, dc)

        # Validaciones globales (críticas) cruzadas
        global_issues: List[Dict] = []
        r1 = self.safe_call(
            scr._validate_feed_mismatches_global,
            nodes,
            default=[],
            title="Validación",
            user_message="No se pudieron evaluar algunas validaciones globales (best-effort).",
            log_message="_validate_feed_mismatches_global failed",
        )
        if r1.ok and r1.value:
            global_issues.extend(r1.value)

        r2 = self.safe_call(
            scr._validate_cross_global,
            nodes,
            default=[],
            title="Validación",
            user_message="No se pudieron evaluar algunas validaciones globales (best-effort).",
            log_message="_validate_cross_global failed",
        )
        if r2.ok and r2.value:
            global_issues.extend(r2.value)

        if global_issues:
            seen = set()
            merged = []
            for it in (issues + global_issues):
                key = (it.get("code"), it.get("msg"))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(it)
            issues = merged

        # Validaciones globales (pipeline) desde el DataModel
        try:
            p = getattr(scr.data_model, "proyecto", {}) or {}
            ext = list(ProjectFacade(p).get_validation_issues() or [])
        except Exception:
            log.debug("Reading validation_issues failed (best-effort)", exc_info=True)
            ext = []
        if ext:
            seen = set()
            merged = []
            for it in (issues + ext):
                key = (it.get("code"), it.get("msg"), it.get("context"))
                if key in seen:
                    continue
                seen.add(key)
                merged.append(it)
            issues = merged

        self.issues_presenter.render(issues, layer)
