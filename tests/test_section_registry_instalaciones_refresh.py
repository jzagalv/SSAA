# -*- coding: utf-8 -*-
from __future__ import annotations

from app.section_registry import build_refresh_actions
from app.sections import Refresh


class _DummyApp:
    def __init__(self, location_screen) -> None:
        self.location_screen = location_screen


class _DummyLocationWithReload:
    def __init__(self) -> None:
        self.reload_calls = 0
        self.refresh_calls = 0
        self.combo_calls = 0
        self.tables_calls = 0
        self.load_calls = 0

    def reload_from_project(self) -> None:
        self.reload_calls += 1

    def refresh_from_model(self, reason: str = "", force: bool = False) -> None:
        _ = reason, force
        self.refresh_calls += 1

    def actualizar_combobox_salas(self) -> None:
        self.combo_calls += 1

    def actualizar_tablas(self) -> None:
        self.tables_calls += 1

    def load_data(self) -> None:
        self.load_calls += 1


class _DummyLocationWithRefreshOnly:
    def __init__(self) -> None:
        self.refresh_calls = []
        self.combo_calls = 0
        self.tables_calls = 0
        self.load_calls = 0

    def refresh_from_model(self, reason: str = "", force: bool = False) -> None:
        self.refresh_calls.append((reason, bool(force)))

    def actualizar_combobox_salas(self) -> None:
        self.combo_calls += 1

    def actualizar_tablas(self) -> None:
        self.tables_calls += 1

    def load_data(self) -> None:
        self.load_calls += 1


class _DummyLocationWithRefreshLegacyNoArgs:
    def __init__(self) -> None:
        self.refresh_calls = 0
        self.combo_calls = 0
        self.tables_calls = 0
        self.load_calls = 0

    def refresh_from_model(self) -> None:
        self.refresh_calls += 1

    def actualizar_combobox_salas(self) -> None:
        self.combo_calls += 1

    def actualizar_tablas(self) -> None:
        self.tables_calls += 1

    def load_data(self) -> None:
        self.load_calls += 1


def test_refresh_instalaciones_prefers_reload_from_project():
    scr = _DummyLocationWithReload()
    app = _DummyApp(scr)
    actions = build_refresh_actions(app=app)

    actions[Refresh.INSTALACIONES]()

    assert scr.reload_calls == 1
    assert scr.refresh_calls == 0
    assert scr.combo_calls == 0
    assert scr.tables_calls == 0
    assert scr.load_calls == 0


def test_refresh_instalaciones_uses_refresh_from_model_when_reload_missing():
    scr = _DummyLocationWithRefreshOnly()
    app = _DummyApp(scr)
    actions = build_refresh_actions(app=app)

    actions[Refresh.INSTALACIONES]()

    assert scr.refresh_calls == [("orchestrator", True)]
    assert scr.combo_calls == 0
    assert scr.tables_calls == 0
    assert scr.load_calls == 0


def test_refresh_instalaciones_supports_legacy_refresh_signature():
    scr = _DummyLocationWithRefreshLegacyNoArgs()
    app = _DummyApp(scr)
    actions = build_refresh_actions(app=app)

    actions[Refresh.INSTALACIONES]()

    assert scr.refresh_calls == 1
    assert scr.combo_calls == 0
    assert scr.tables_calls == 0
    assert scr.load_calls == 0
