# -*- coding: utf-8 -*-
"""SectionOrchestrator

Single place that executes SECTION_GRAPH actions.

Design goals:
- Best-effort: never crash the UI.
- No PyQt dependency.
- Keep the controller small and free of cross-screen refresh logic.

The orchestrator receives the *app object* (BatteryBankCalculatorApp) because
refresh actions need to call screen methods. Those calls are guarded.
"""

from __future__ import annotations

from app.section_registry import build_recalc_actions, build_refresh_actions

import logging
from typing import Any, Callable

from infra.perf import span as perf_span

from services.section_graph import SECTION_GRAPH

log = logging.getLogger(__name__)


def _safe_call(fn: Callable[[], Any], *, label: str) -> None:
    try:
        with perf_span(label, threshold_ms=50.0):
            fn()
    except Exception:
        log.debug(f"{label} failed", exc_info=True)


class SectionOrchestrator:
    def __init__(self, *, app, data_model, calc_service, validation_service, event_bus=None):
        self.app = app
        self.dm = data_model
        self.calc_service = calc_service
        self.validation_service = validation_service


        # Precompute action maps (single source of truth)
        self._recalc_actions = build_recalc_actions(app=app, calc_service=calc_service)
        self._refresh_actions = build_refresh_actions(app=app)
        self._event_bus = event_bus
        if self._event_bus is not None:
            try:
                from app.events import MetadataChanged, InputChanged, ModelChanged
                self._event_bus.subscribe(MetadataChanged, self._on_metadata_changed)
                self._event_bus.subscribe(InputChanged, self._on_input_changed)
                self._event_bus.subscribe(ModelChanged, self._on_model_changed)
            except Exception:
                log.debug("Failed to subscribe to EventBus (best-effort).", exc_info=True)

    # ---------------- public API ----------------
    def on_section_changed(self, section) -> None:
        """Handle a change notification.

        *section* must be a Section enum in normal operation.
        In release we tolerate strings (coerce), but in debug we fail fast.
        """
        sec = self._norm_section(section)
        if sec is None:
            return
        spec = SECTION_GRAPH.get(sec)
        if not spec:
            return
        self._run_spec(sec, spec)

    def on_section_viewed(self, section) -> None:
        """Handle a *view activation* (tab change).

        Root-cause performance fix:
        - Viewing a screen must NOT trigger recalculation.
        - We only run the declared *refresh* actions for that section.
        """
        sec = self._norm_section(section)
        if sec is None:
            return
        spec = SECTION_GRAPH.get(sec)
        if not spec:
            return
        dm = self.dm
        if hasattr(dm, "set_ui_refreshing"):
            dm.set_ui_refreshing(True)
        try:
            for key in (spec.refresh or []):
                self._refresh(key)
        finally:
            if hasattr(dm, "set_ui_refreshing"):
                dm.set_ui_refreshing(False)

    def on_project_loaded(self) -> None:
        from app.sections import Section
        spec = SECTION_GRAPH.get(Section.PROJECT_LOADED)
        if not spec:
            return
        self._run_spec(Section.PROJECT_LOADED, spec)

    # ---------------- EventBus handlers ----------------
    def _on_metadata_changed(self, event) -> None:
        from app.sections import Section
        if getattr(event, "section", None) != Section.CC:
            return
        scr = getattr(self.app, "cc_screen", None)
        if scr is not None and hasattr(scr, "refresh_metadata"):
            _safe_call(lambda: scr.refresh_metadata(getattr(event, "fields", None)), label="cc metadata refresh")

    def _on_input_changed(self, event) -> None:
        from app.sections import Section
        if getattr(event, "section", None) != Section.CC:
            return
        # CC input recompute is handled by the compute orchestrator.
        return

    def _on_model_changed(self, event) -> None:
        from app.sections import Section
        if getattr(event, "section", None) != Section.CC:
            return
        scr = getattr(self.app, "cc_screen", None)
        if scr is not None and hasattr(scr, "refresh_from_model"):
            _safe_call(lambda: scr.refresh_from_model(), label="cc model refresh")

    # ---------------- internals ----------------
    def _run_spec(self, section, spec) -> None:
        dm = self.dm
        if hasattr(dm, "set_ui_refreshing"):
            dm.set_ui_refreshing(True)
        try:
            # 1) Recalc
            for key in (spec.recalc or []):
                self._recalc(key)

            # 2) Validate
            if spec.validate:
                vals = []
                for s in (spec.validate or []):
                    sec = self._norm_section(s)
                    if sec is None:
                        continue
                    vals.append(sec)
                self.validation_service.validate_sections(vals)

            # 3) Refresh UI
            for key in (spec.refresh or []):
                self._refresh(key)
        finally:
            if hasattr(dm, "set_ui_refreshing"):
                dm.set_ui_refreshing(False)

    def _recalc(self, key) -> None:
        from app.sections import Section
        sec = self._norm_section(key)
        if sec is None:
            return
        fn = self._recalc_actions.get(sec)
        if fn is None:
            return
        _safe_call(fn, label=f"recalc {sec}")

    def _refresh(self, key) -> None:
        from app.sections import Refresh
        ref = self._norm_refresh(key)
        if ref is None:
            return
        fn = self._refresh_actions.get(ref)
        if fn is None:
            return
        _safe_call(fn, label=f"refresh {ref}")

    @staticmethod
    def _norm_section(section):
        """Normalize to Section.

        In debug: reject non-enum inputs to avoid hidden hydras.
        In release: try to coerce from string.
        """
        from app.sections import Section
        if section is None:
            return None
        if isinstance(section, Section):
            return section
        if __debug__:
            raise TypeError(f"Expected Section enum, got: {type(section).__name__}")
        try:
            return Section(str(section))
        except Exception:
            return None

    @staticmethod
    def _norm_refresh(refresh):
        """Normalize to Refresh.

        In debug: reject non-enum inputs to avoid hidden hydras.
        In release: try to coerce from string.
        """
        from app.sections import Refresh
        if refresh is None:
            return None
        if isinstance(refresh, Refresh):
            return refresh
        if __debug__:
            raise TypeError(f"Expected Refresh enum, got: {type(refresh).__name__}")
        try:
            return Refresh(str(refresh))
        except Exception:
            return None
