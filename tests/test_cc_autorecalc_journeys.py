# -*- coding: utf-8 -*-
"""Journeys for CC auto-recalc (PyQt-free)."""

from app.events import EventBus, InputChanged, Computed
from app.sections import Section
from services.compute.orchestrator_core import ComputeOrchestratorCore, is_stale_result
from services.compute.cc_compute_service import CCComputeService
from storage.project_serialization import apply_project_dict, to_project_dict
from data_model import DataModel


def test_debounce_coalesces_marks():
    core = ComputeOrchestratorCore(debounce_ms=200)
    for i in range(10):
        core.mark_dirty(Section.CC, now=0.01 * i)
    assert core.should_run(now=0.05) is False
    assert core.should_run(now=0.3) is True
    assert is_stale_result(2, 1) is True
    assert is_stale_result(2, 2) is False


def test_no_loop_on_computed():
    bus = EventBus()
    events = []

    def on_input(ev):
        events.append(("InputChanged", ev.section))
        res = CCComputeService().compute({"instalaciones": {"gabinetes": []}})
        bus.emit(Computed(section=Section.CC, reason="test"))

    def on_computed(ev):
        events.append(("Computed", ev.section))

    bus.subscribe(InputChanged, on_input)
    bus.subscribe(Computed, on_computed)

    bus.emit(InputChanged(section=Section.CC, fields={"reason": "test"}))

    assert events.count(("InputChanged", Section.CC)) == 1
    assert events.count(("Computed", Section.CC)) == 1


def test_cc_results_not_persisted_on_roundtrip():
    data = {
        "_meta": {},
        "proyecto": {
            "cc_escenarios": {"1": "A"},
            "cc_results": {"totals": {"p_total": 10.0}},
        },
        "instalaciones": {"gabinetes": [], "ubicaciones": []},
        "componentes": {},
    }
    dm = DataModel()
    apply_project_dict(dm, data)
    res = CCComputeService().compute(dm.proyecto)
    dm.set_cc_results(res, notify=False)
    out = to_project_dict(dm)
    assert "cc_results" not in (out.get("proyecto") or {})
    assert (out.get("proyecto") or {}).get("cc_escenarios", {}).get("1") == "A"
