# -*- coding: utf-8 -*-
"""Qt-backed compute orchestrator (debounced, QThreadPool/QRunnable)."""
from __future__ import annotations

import logging
from typing import Any

from services.compute.orchestrator_core import ComputeOrchestratorCore, is_stale_result
from services.compute.cc_compute_worker import CCComputeWorker

log = logging.getLogger(__name__)

try:
    from PyQt5.QtCore import QObject, QTimer, QThreadPool
except Exception:  # pragma: no cover - optional for test environments
    QObject = None
    QTimer = None


if QObject is not None:

    class QtComputeOrchestrator(QObject):
        def __init__(self, *, event_bus: Any, data_model: Any, debounce_ms: int = 200) -> None:
            super().__init__()
            self._bus = event_bus
            self._dm = data_model
            self._core = ComputeOrchestratorCore(debounce_ms=debounce_ms)
            self._pool = QThreadPool.globalInstance()
            self._current_compute_id = 0
            self._running_compute_id = None
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(int(debounce_ms))
            self._timer.timeout.connect(self._run_compute)
            self._computing = False
            self._rerun = False

            if self._bus is not None:
                try:
                    from app.events import InputChanged, MetadataChanged
                    self._bus.subscribe(InputChanged, self._on_dirty_event)
                    self._bus.subscribe(MetadataChanged, self._on_dirty_event)
                except Exception:
                    log.debug("Failed to subscribe compute orchestrator (best-effort).", exc_info=True)

        def _on_dirty_event(self, event) -> None:
            from app.sections import Section
            if getattr(event, "section", None) != Section.CC:
                return
            self._core.mark_dirty(Section.CC)
            self._schedule()

        def _schedule(self) -> None:
            try:
                self._timer.start()
            except Exception:
                self._run_compute()

        def force_compute(self, section, reason: str = "manual") -> None:
            self._core.mark_dirty(section)
            self._run_compute(reason=reason, force=True)

        def _run_compute(self, *, reason: str = "auto", force: bool = False) -> None:
            if self._computing:
                self._rerun = True
                return
            if not force and not self._core.should_run():
                return
            dirty = self._core.pop_dirty()
            if not dirty:
                return
            self._computing = True
            try:
                from app.sections import Section
                if Section.CC not in dirty:
                    self._computing = False
                    return
                self._current_compute_id += 1
                compute_id = self._current_compute_id
                self._running_compute_id = compute_id
                log.debug("CC compute start id=%s", compute_id)
                try:
                    from app.events import ComputeStarted
                    from app.sections import Section
                    if self._bus is not None:
                        self._bus.emit(ComputeStarted(section=Section.CC, reason=reason))
                except Exception:
                    log.debug("ComputeStarted emit failed (best-effort).", exc_info=True)

                snapshot = {}
                if hasattr(self._dm, "get_cc_inputs_snapshot"):
                    snapshot = self._dm.get_cc_inputs_snapshot()
                else:
                    proj = getattr(self._dm, "proyecto", {}) or {}
                    snapshot = proj if isinstance(proj, dict) else {}

                worker = CCComputeWorker(snapshot, compute_id)
                worker.signals.finished.connect(lambda cid, res: self._on_compute_finished(cid, res, reason))
                worker.signals.error.connect(self._on_compute_error)
                self._pool.start(worker)
            except Exception:
                self._computing = False
                log.debug("Compute run failed (best-effort).", exc_info=True)

        def _on_compute_finished(self, compute_id: int, results: dict, reason: str) -> None:
            try:
                if is_stale_result(self._current_compute_id, compute_id):
                    log.debug("Discarding stale CC result id=%s current=%s", compute_id, self._current_compute_id)
                    return
                if hasattr(self._dm, "set_cc_results"):
                    self._dm.set_cc_results(results, notify=False)
                bus = self._bus
                if bus is not None:
                    from app.events import Computed
                    from app.sections import Section
                    bus.emit(Computed(section=Section.CC, reason=reason))
            finally:
                self._computing = False
                self._running_compute_id = None
                if self._rerun or self._core.has_dirty():
                    self._rerun = False
                    self._schedule()

        def _on_compute_error(self, compute_id: int, exc: object) -> None:
            detail = exc
            if isinstance(exc, tuple) and len(exc) == 2:
                detail = exc[0]
            log.error("CC compute error id=%s: %r", compute_id, detail)
            self._computing = False
            self._running_compute_id = None
            # Re-schedule if new inputs arrived during compute
            if self._rerun or self._core.has_dirty():
                self._rerun = False
                self._schedule()

else:

    class QtComputeOrchestrator:  # pragma: no cover
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("PyQt5 is required to use QtComputeOrchestrator")
