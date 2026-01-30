# -*- coding: utf-8 -*-
"""Bank/Charger update pipeline.

This module centralizes the sequence of UI/model updates that must run after
user edits (profile changes, IEEE Kt edits, etc.).

Design notes
------------
* Keeps the screen thin: the screen triggers `pipeline.on_*()` methods.
* Keeps the controller thin: the controller owns the pipeline instance.
* Presenters do rendering; controller methods do orchestration/persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BankChargerUpdatePipeline:
    """Coordinates a safe, deterministic refresh sequence for Bank/Charger."""

    screen: object
    controller: object

    def on_profile_changed(self) -> None:
        """Called when the load profile (tbl_cargas) changes."""
        scr = self.screen

        # 1) Normalize/autocalc and persist profile
        scr._refresh_perfil_autocalc()
        scr._save_perfil_cargas_to_model()

        # 2) Invalidate bundle caches (selection depends on profile & IEEE)
        scr._invalidate_bc_bundle()

        # 3) Refresh dependent UI in the correct order
        scr._update_cycle_table()      # builds duty-cycle cache used elsewhere
        scr._update_profile_chart()    # purely visual
        scr._update_ieee485_table()    # uses duty-cycle cache
        scr._update_selection_tables() # uses sizing + IEEE results
        scr._update_summary_table()    # depends on selection

        # 4) Any deferred housekeeping already used by the screen
        scr._schedule_updates()

    def on_ieee_kt_changed(self) -> None:
        """Called when user edits Kt values in IEEE table."""
        scr = self.screen

        scr._persist_ieee_kt_to_model()
        scr._invalidate_bc_bundle()

        # Re-render IEEE (Pos/Neg/totals) and then downstream tables
        scr._update_ieee485_table()
        scr._update_selection_tables()
        scr._update_summary_table()

        scr._schedule_updates()

    def full_refresh(self, *, reason: Optional[str] = None) -> None:
        """A conservative full refresh (safe for project load / tab switch)."""
        # Today, the screen already has recalculate_all() which runs the sizing
        # and updates several tables. We keep this as a simple adapter.
        self.screen.recalculate_all()
