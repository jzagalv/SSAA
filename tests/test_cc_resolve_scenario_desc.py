# -*- coding: utf-8 -*-
"""Unit tests for resolve_scenario_desc (PyQt-free)."""
from __future__ import annotations

from screens.cc_consumption.utils import resolve_scenario_desc


def test_resolve_desc_prev_placeholder_db_real():
    assert resolve_scenario_desc(1, "Escenario 1", "87B") == "87B"


def test_resolve_desc_prev_real_db_same():
    assert resolve_scenario_desc(1, "87B", "87B") == "87B"


def test_resolve_desc_prev_empty_db_real():
    assert resolve_scenario_desc(1, "", "87B") == "87B"


def test_resolve_desc_prev_placeholder_db_empty():
    assert resolve_scenario_desc(1, "Escenario 1", "") == "Escenario 1"


def test_resolve_desc_prev_real_db_other():
    assert resolve_scenario_desc(1, "Mi Escenario", "87B") == "Mi Escenario"


def test_resolve_desc_prev_placeholder_db_placeholder():
    assert resolve_scenario_desc(1, "Escenario 1", "Escenario 1") == "Escenario 1"
