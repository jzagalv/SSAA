# -*- coding: utf-8 -*-
"""Unit tests for AleatoriosTableLogic (PyQt-free)."""
from __future__ import annotations

from screens.cc_consumption.models.aleatorios_table_model import AleatoriosTableLogic


class _StubController:
    def __init__(self):
        self._selected = {}
        self.calls = []

    def get_random_selected(self, comp_id: str) -> bool:
        return bool(self._selected.get(comp_id, False))

    def set_random_selected(self, comp_id: str, selected: bool) -> bool:
        self.calls.append((comp_id, selected))
        prev = bool(self._selected.get(comp_id, False))
        self._selected[comp_id] = bool(selected)
        return prev != bool(selected)


def test_logic_set_items_and_selection():
    ctrl = _StubController()
    logic = AleatoriosTableLogic(ctrl)

    items = [
        type("X", (), {"comp_id": "c1", "gab_tag": "G1", "gab_nombre": "Gab", "tag_comp": "T1", "desc": "D1", "p_eff": 10.0, "i_eff": 0.1})(),
        type("X", (), {"comp_id": "c2", "gab_tag": "G2", "gab_nombre": "Gab2", "tag_comp": "T2", "desc": "D2", "p_eff": 20.0, "i_eff": 0.2})(),
    ]

    logic.set_items(items)
    assert logic.row_count() == 2
    assert logic.row_at(0).comp_id == "c1"

    assert logic.get_selected("c1") is False
    changed = logic.set_selected("c1", True)
    assert changed is True
    assert logic.get_selected("c1") is True
    assert ctrl.calls == [("c1", True)]
