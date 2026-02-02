# -*- coding: utf-8 -*-
"""Rules for persisting scenario descriptions (PyQt-free)."""

from screens.cc_consumption.utils import is_placeholder, should_persist_scenario_desc, persist_desc_if_real


def test_should_persist_scenario_desc_rules():
    assert should_persist_scenario_desc(1, "") is False
    assert should_persist_scenario_desc(1, "Escenario 1") is False
    assert should_persist_scenario_desc(1, "87B") is True


def test_persist_desc_if_real_keeps_existing_on_placeholder():
    existing = {"1": "87B"}
    out = persist_desc_if_real(existing.copy(), 1, "Escenario 1")
    assert out.get("1") == "87B"
    assert is_placeholder(1, "Escenario 1") is True
