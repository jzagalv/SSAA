# -*- coding: utf-8 -*-
from __future__ import annotations

from app.section_registry import build_refresh_actions
from app.sections import Refresh


class _DummyApp:
    def __init__(self, bank_screen) -> None:
        self.bank_screen = bank_screen


class _DummyBankWithRefresh:
    def __init__(self) -> None:
        self.refresh_calls = []
        self.reload_calls = 0
        self.reload_data_calls = 0
        self.load_data_calls = 0

    def refresh_from_model(self, reason: str = "", force: bool = False) -> None:
        self.refresh_calls.append((reason, bool(force)))

    def reload_from_project(self) -> None:
        self.reload_calls += 1

    def reload_data(self) -> None:
        self.reload_data_calls += 1

    def load_data(self) -> None:
        self.load_data_calls += 1


class _DummyBankWithReloadOnly:
    def __init__(self) -> None:
        self.reload_calls = 0
        self.reload_data_calls = 0
        self.load_data_calls = 0

    def reload_from_project(self) -> None:
        self.reload_calls += 1

    def reload_data(self) -> None:
        self.reload_data_calls += 1

    def load_data(self) -> None:
        self.load_data_calls += 1


def test_refresh_bank_charger_prefers_refresh_from_model():
    scr = _DummyBankWithRefresh()
    app = _DummyApp(scr)
    actions = build_refresh_actions(app=app)

    actions[Refresh.BANK_CHARGER]()

    assert scr.refresh_calls == [("orchestrator", True)]
    assert scr.reload_calls == 0
    assert scr.reload_data_calls == 0
    assert scr.load_data_calls == 0


def test_refresh_bank_charger_falls_back_to_reload_from_project():
    scr = _DummyBankWithReloadOnly()
    app = _DummyApp(scr)
    actions = build_refresh_actions(app=app)

    actions[Refresh.BANK_CHARGER]()

    assert scr.reload_calls == 1
    assert scr.reload_data_calls == 0
    assert scr.load_data_calls == 0
