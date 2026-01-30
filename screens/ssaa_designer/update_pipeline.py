# -*- coding: utf-8 -*-
"""SSAA Designer - Update pipeline

Centraliza la secuencia de refrescos/post-procesos después de mutar la topología.

Objetivo:
- Evitar duplicación de llamadas (persist, rebuild edges, refresh feeders, issues, etc.)
- Mantener un orden determinístico (reduce bugs y facilita futuros refactors)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SSaaDesignerUpdatePipeline:
    """Orquestador de refrescos para SSAA Designer."""

    screen: object
    controller: object

    def after_topology_mutation(
        self,
        *,
        rebuild_edges: bool = False,
        recompute_load_table: bool = False,
        refresh_feeders: bool = False,
        refresh_issues: bool = True,
    ) -> None:
        """Llamar después de agregar/eliminar/mover nodos o aristas."""
        # 1) Persistir al modelo
        try:
            self.controller.persist()
        except Exception:
            # La pantalla ya está hardeneada con safe_slot; pero esto puede
            # invocarse desde otros contextos.
            pass

        # 2) Rebuild edges
        if rebuild_edges and hasattr(self.screen, "_rebuild_all_edges"):
            try:
                self.screen._rebuild_all_edges()
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        # 3) Tabla de cargas aguas abajo (si existe)
        if recompute_load_table and hasattr(self.screen, "_compute_load_table_rows"):
            try:
                self.screen._compute_load_table_rows()
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        # 4) Issues
        if refresh_issues:
            try:
                self.controller.refresh_issues_panel()
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        # 5) Alimentadores disponibles
        if refresh_feeders and hasattr(self.screen, "_refresh_feeders_table"):
            try:
                self.screen._refresh_feeders_table()
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
