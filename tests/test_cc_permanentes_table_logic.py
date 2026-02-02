# -*- coding: utf-8 -*-
"""Unit tests for PermanentesTableLogic (PyQt-free)."""
from __future__ import annotations

from screens.cc_consumption.models.permanentes_table_model import PermanentesTableLogic


class _Item:
    def __init__(self, comp_id: str, p_eff: float, gab_tag="G1", gab_nombre="Gab", tag_comp="T1", desc="D1", comp=None):
        self.comp_id = comp_id
        self.p_eff = p_eff
        self.gab_tag = gab_tag
        self.gab_nombre = gab_nombre
        self.tag_comp = tag_comp
        self.desc = desc
        self.comp = comp or {}


def test_logic_set_items_custom_pct():
    logic = PermanentesTableLogic()
    items = [
        _Item("c1", 100.0, comp={"data": {"cc_perm_pct_custom": "25"}}),
    ]

    def get_custom_pct(comp_data):
        return 25.0

    logic.set_items(items, use_global=False, pct_global=50.0, get_custom_pct=get_custom_pct, vmin=100.0)
    assert logic.row_count() == 1
    row = logic.row_at(0)
    assert row is not None
    assert row.pct == 25.0
    assert round(row.p_perm, 2) == 25.00
    assert round(row.p_mom, 2) == 75.00
    assert round(row.i_perm, 2) == 0.25
    assert round(row.i_out, 2) == 0.75


def test_logic_apply_global_pct():
    logic = PermanentesTableLogic()
    items = [
        _Item("c1", 50.0),
        _Item("c2", 50.0),
    ]

    logic.set_items(items, use_global=True, pct_global=10.0, get_custom_pct=lambda _d: 0.0, vmin=100.0)
    logic.apply_global_pct(80.0, 100.0)
    row = logic.row_at(0)
    assert row is not None
    assert round(row.pct, 2) == 80.0
    assert round(row.p_perm, 2) == 40.00
