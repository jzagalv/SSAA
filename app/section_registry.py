# -*- coding: utf-8 -*-
"""Section registry

Centralizes:
- recalc handlers
- refresh handlers

So the orchestrator doesn't grow into a hydra again.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict

from app.sections import Section, Refresh

log = logging.getLogger(__name__)


def build_recalc_actions(*, app, calc_service) -> Dict[Section, Callable[[], None]]:
    """Return mapping: Section -> callable (best-effort executed by orchestrator)."""

    def recalc_cc():
        orch = getattr(app, "compute_orchestrator", None)
        if orch is not None and hasattr(orch, "force_compute"):
            try:
                orch.force_compute(Section.CC, reason="recalc")
                return
            except Exception:
                log.debug("compute orchestrator recalc failed (best-effort).", exc_info=True)
        calc_service.recalc_cc()

    def recalc_bank_charger():
        # Prefer screen cache path because it holds duty-cycle caches.
        scr = getattr(app, "bank_screen", None)
        if scr is not None and hasattr(scr, "_get_bc_bundle"):
            scr._get_bc_bundle()
        else:
            # fallback (may be no-op if inputs missing)
            if hasattr(calc_service, "recalc_bank_charger"):
                calc_service.recalc_bank_charger()

    return {
        Section.CC: recalc_cc,
        Section.BANK_CHARGER: recalc_bank_charger,
    }


def build_refresh_actions(*, app) -> Dict[Refresh, Callable[[], None]]:
    """Return mapping: Refresh -> callable (best-effort executed by orchestrator)."""

    def refresh_main():
        scr = getattr(app, "main_screen", None)
        if scr is not None and hasattr(scr, "load_data"):
            scr.load_data()

    def refresh_instalaciones():
        scr = getattr(app, "location_screen", None)
        if scr is None:
            return
        reload_fn = getattr(scr, "reload_from_project", None)
        if callable(reload_fn):
            try:
                reload_fn()
                return
            except Exception:
                log.debug("refresh_instalaciones.reload_from_project failed (best-effort).", exc_info=True)

        refresh_fn = getattr(scr, "refresh_from_model", None)
        if callable(refresh_fn):
            try:
                try:
                    refresh_fn(reason="orchestrator", force=True)
                except TypeError:
                    refresh_fn()
                return
            except Exception:
                log.debug("refresh_instalaciones.refresh_from_model failed (best-effort).", exc_info=True)

        try:
            if hasattr(scr, "actualizar_combobox_salas"):
                scr.actualizar_combobox_salas()
            if hasattr(scr, "actualizar_tablas"):
                scr.actualizar_tablas()
            elif hasattr(scr, "load_data"):
                scr.load_data()
        except Exception:
            log.debug("refresh_instalaciones legacy fallback failed (best-effort).", exc_info=True)

    def refresh_cabinet():
        scr = getattr(app, "cabinet_screen", None)
        if scr is None:
            return
        for name in ("load_cabinets", "load_equipment", "load_data"):
            if hasattr(scr, name):
                getattr(scr, name)()

    def refresh_board_feed():
        scr = getattr(app, "board_feed_screen", None)
        if scr is not None and hasattr(scr, "load_data"):
            scr.load_data()

    def refresh_cc():
        scr = getattr(app, "cc_screen", None)
        if scr is None:
            return
        if hasattr(scr, "refresh_from_model"):
            scr.refresh_from_model()
        elif hasattr(scr, "reload_data"):
            scr.reload_data()

    def refresh_bank_charger():
        scr = getattr(app, "bank_screen", None)
        if scr is None:
            return
        refresh_fn = getattr(scr, "refresh_from_model", None)
        if callable(refresh_fn):
            try:
                try:
                    refresh_fn(reason="orchestrator", force=True)
                except TypeError:
                    refresh_fn()
                return
            except Exception:
                log.debug("refresh_bank_charger.refresh_from_model failed (best-effort).", exc_info=True)

        reload_fn = getattr(scr, "reload_from_project", None)
        if callable(reload_fn):
            try:
                reload_fn()
                return
            except Exception:
                log.debug("refresh_bank_charger.reload_from_project failed (best-effort).", exc_info=True)

        try:
            if hasattr(scr, "reload_data"):
                scr.reload_data()
            elif hasattr(scr, "load_data"):
                scr.load_data()
        except Exception:
            log.debug("refresh_bank_charger legacy fallback failed (best-effort).", exc_info=True)

    def refresh_designer():
        scr = getattr(app, "ssaa_designer_screen", None)
        if scr is None:
            return
        if hasattr(scr, "reload_from_project"):
            scr.reload_from_project()
        elif hasattr(scr, "load_data"):
            scr.load_data()
        # refresh issues panel if available
        if hasattr(scr, "_refresh_issues_panel"):
            scr._refresh_issues_panel()
        elif hasattr(scr, "refresh_issues_panel"):
            scr.refresh_issues_panel()

    def refresh_load_tables():
        scr = getattr(app, "load_tables_screen", None)
        if scr is None:
            return
        if hasattr(scr, "reload_from_project"):
            scr.reload_from_project()
        elif hasattr(scr, "load_from_model"):
            scr.load_from_model()
        elif hasattr(scr, "load_data"):
            scr.load_data()

    return {
        Refresh.MAIN: refresh_main,
        Refresh.INSTALACIONES: refresh_instalaciones,
        Refresh.CABINET: refresh_cabinet,
        Refresh.BOARD_FEED: refresh_board_feed,
        Refresh.CC: refresh_cc,
        Refresh.BANK_CHARGER: refresh_bank_charger,
        Refresh.DESIGNER: refresh_designer,
        Refresh.LOAD_TABLES: refresh_load_tables,
    }
