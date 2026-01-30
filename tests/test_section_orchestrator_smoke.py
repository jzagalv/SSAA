# -*- coding: utf-8 -*-

from __future__ import annotations

from app.sections import Section


class _DummyDM:
    def __init__(self):
        self.ui_refreshing = False

    def set_ui_refreshing(self, v: bool):
        self.ui_refreshing = bool(v)


class _DummyCalc:
    def __init__(self, calls: list[str]):
        self.calls = calls

    def recalc_cc(self):
        self.calls.append("recalc_cc")

    def recalc_bank_charger(self, *args, **kwargs):
        self.calls.append("recalc_bank_charger")


class _DummyVal:
    def __init__(self, calls: list[str]):
        self.calls = calls

    def validate_sections(self, sections):
        self.calls.append("validate:" + ",".join(map(str, sections or [])))


class _DummyScreen:
    def __init__(self, calls: list[str], name: str, method: str):
        self.calls = calls
        self._name = name
        self._method = method

    def __getattr__(self, item):
        if item == self._method:
            def _fn():
                self.calls.append(f"refresh:{self._name}")
            return _fn
        raise AttributeError(item)


class _DummyApp:
    def __init__(self, calls: list[str]):
        # Match names expected by section_registry
        self.main_screen = _DummyScreen(calls, "main", "load_data")
        self.location_screen = _DummyScreen(calls, "instalaciones", "actualizar_tablas")
        self.cabinet_screen = _DummyScreen(calls, "cabinet", "load_data")
        self.board_feed_screen = _DummyScreen(calls, "board_feed", "load_data")
        self.cc_screen = _DummyScreen(calls, "cc", "reload_data")
        self.bank_screen = _DummyScreen(calls, "bank_charger", "reload_from_project")
        self.ssaa_designer_screen = _DummyScreen(calls, "designer", "reload_from_project")
        self.load_tables_screen = _DummyScreen(calls, "load_tables", "reload_from_project")


def test_orchestrator_cc_flow_smoke():
    from services.section_orchestrator import SectionOrchestrator
    from app.sections import Section

    calls: list[str] = []
    dm = _DummyDM()
    app = _DummyApp(calls)
    calc = _DummyCalc(calls)
    val = _DummyVal(calls)

    orch = SectionOrchestrator(app=app, data_model=dm, calc_service=calc, validation_service=val)

    orch.on_section_changed(Section.CC)

    assert "recalc_cc" in calls
    assert any(x.startswith("validate:") and "Section.CC" in x for x in calls)
    assert "refresh:cc" in calls
    assert dm.ui_refreshing is False


def test_orchestrator_project_loaded_smoke():
    from services.section_orchestrator import SectionOrchestrator

    calls: list[str] = []
    dm = _DummyDM()
    app = _DummyApp(calls)
    calc = _DummyCalc(calls)
    val = _DummyVal(calls)

    orch = SectionOrchestrator(app=app, data_model=dm, calc_service=calc, validation_service=val)

    orch.on_project_loaded()

    # Should at least attempt both recalcs and refresh main screens.
    assert "recalc_cc" in calls
    assert "refresh:main" in calls
