# -*- coding: utf-8 -*-
from __future__ import annotations

from app.section_registry import build_refresh_actions
from app.sections import Refresh, Section
from services.section_orchestrator import SectionOrchestrator


class _DummyLocation:
    def __init__(self) -> None:
        self.reload_calls = 0
        self.combo_calls = 0
        self.tables_calls = 0

    def reload_from_project(self) -> None:
        self.reload_calls += 1

    def actualizar_combobox_salas(self) -> None:
        self.combo_calls += 1

    def actualizar_tablas(self) -> None:
        self.tables_calls += 1


class _DummyBankScreen:
    def __init__(self) -> None:
        self.refresh_model_calls = []
        self.refresh_project_calls = 0
        self.recalculate_calls = 0

    def refresh_from_model(self, reason: str = "", force: bool = False) -> None:
        self.refresh_model_calls.append((reason, bool(force)))
        self.refresh_from_project()

    def refresh_from_project(self) -> None:
        self.refresh_project_calls += 1
        self.recalculate()

    def recalculate(self) -> None:
        self.recalculate_calls += 1


class _DummyLoadDataScreen:
    def load_data(self) -> None:
        return None


class _DummyReloadScreen:
    def reload_from_project(self) -> None:
        return None


class _DummyCCScreen:
    def refresh_from_model(self, reason: str = "", force: bool = False) -> None:
        _ = reason, force
        return None


class _DummyLoadTablesScreen:
    def reload_from_project(self) -> None:
        return None


class _DummyAppRefreshOnly:
    def __init__(self, location_screen=None, bank_screen=None) -> None:
        self.location_screen = location_screen
        self.bank_screen = bank_screen


def test_refresh_instalaciones_uses_reload_from_project_contract() -> None:
    scr = _DummyLocation()
    app = _DummyAppRefreshOnly(location_screen=scr)
    actions = build_refresh_actions(app=app)

    actions[Refresh.INSTALACIONES]()

    assert scr.reload_calls == 1
    assert scr.combo_calls == 0
    assert scr.tables_calls == 0


def test_refresh_bank_charger_contract_calls_refresh_and_recalculate() -> None:
    scr = _DummyBankScreen()
    app = _DummyAppRefreshOnly(bank_screen=scr)
    actions = build_refresh_actions(app=app)

    actions[Refresh.BANK_CHARGER]()

    assert scr.refresh_model_calls == [("orchestrator", True)]
    assert scr.refresh_project_calls == 1
    assert scr.recalculate_calls == 1


class _DummyDM:
    def __init__(self) -> None:
        self.ui_refreshing = False

    def set_ui_refreshing(self, v: bool) -> None:
        self.ui_refreshing = bool(v)


class _DummyCalc:
    def recalc_cc(self) -> None:
        return None

    def recalc_bank_charger(self, *args, **kwargs) -> None:
        _ = args, kwargs
        return None


class _DummyVal:
    def validate_sections(self, sections) -> None:
        _ = sections
        return None


class _DummyAppForOrchestrator:
    def __init__(self, bank_screen) -> None:
        self.main_screen = _DummyLoadDataScreen()
        self.location_screen = _DummyLocation()
        self.cabinet_screen = _DummyLoadDataScreen()
        self.board_feed_screen = _DummyLoadDataScreen()
        self.cc_screen = _DummyCCScreen()
        self.bank_screen = bank_screen
        self.ssaa_designer_screen = _DummyReloadScreen()
        self.load_tables_screen = _DummyLoadTablesScreen()


def test_project_section_change_propagates_bank_charger_refresh() -> None:
    dm = _DummyDM()
    bank = _DummyBankScreen()
    app = _DummyAppForOrchestrator(bank)
    orch = SectionOrchestrator(
        app=app,
        data_model=dm,
        calc_service=_DummyCalc(),
        validation_service=_DummyVal(),
    )

    orch.on_section_changed(Section.PROJECT)

    assert bank.refresh_model_calls == [("orchestrator", True)]
    assert bank.recalculate_calls == 1
