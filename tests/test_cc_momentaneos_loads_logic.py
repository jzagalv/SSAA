# -*- coding: utf-8 -*-
"""Unit tests for MomentaneosLoadsTableLogic (PyQt-free)."""
from __future__ import annotations

from screens.cc_consumption.models.momentaneos_loads_table_model import MomentaneosLoadsTableLogic


class _Item:
    def __init__(self, comp_id: str, p_eff: float, i_eff: float, incluir=True, escenario=1):
        self.comp_id = comp_id
        self.gab_tag = "G1"
        self.gab_nombre = "Gab"
        self.tag_comp = "T1"
        self.desc = "D1"
        self.p_eff = p_eff
        self.i_eff = i_eff
        self.mom_incluir = incluir
        self.mom_escenario = escenario


def test_logic_set_items_basic():
    logic = MomentaneosLoadsTableLogic()
    items = [_Item("c1", 100.0, 1.0, incluir=False, escenario=2)]
    logic.set_items(items)
    assert logic.row_count() == 1
    row = logic.row_at(0)
    assert row is not None
    assert row.comp_id == "c1"
    assert row.incluir is False
    assert row.escenario == 2


def test_logic_set_incluir_and_escenario():
    logic = MomentaneosLoadsTableLogic()
    items = [_Item("c1", 100.0, 1.0)]
    logic.set_items(items)
    assert logic.set_incluir(0, False) is True
    assert logic.set_escenario(0, 3) is True
    row = logic.row_at(0)
    assert row.incluir is False
    assert row.escenario == 3
