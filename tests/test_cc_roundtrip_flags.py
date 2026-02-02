# -*- coding: utf-8 -*-
"""Roundtrip tests for CC flags (aleatorio selection and momentary flags)."""
from __future__ import annotations

from data_model import DataModel
from screens.cc_consumption.cc_consumption_controller import CCConsumptionController
from domain.cc_consumption import iter_cc_items, get_model_gabinetes


def _mk_dm_with_component(comp: dict) -> DataModel:
    dm = DataModel()
    gab = {
        "tag": "G1",
        "nombre": "Gab1",
        "components": [comp],
    }
    gabs = [gab]
    dm.instalaciones["gabinetes"] = gabs
    dm.gabinetes = dm.instalaciones["gabinetes"]
    return dm


def test_aleatorio_selection_roundtrip():
    comp = {
        "id": "c1",
        "name": "Comp1",
        "data": {
            "tipo_consumo": "C.C. aleatorio",
            "potencia_w": 100.0,
        },
    }
    dm = _mk_dm_with_component(comp)
    ctrl = CCConsumptionController(dm)

    assert ctrl.set_random_selected("c1", True) is True
    assert comp["data"].get("cc_aleatorio_sel") is True

    items = iter_cc_items(dm.proyecto, get_model_gabinetes(dm))
    item = next((it for it in items if it.comp_id == "c1"), None)
    assert item is not None
    assert item.ale_sel is True


def test_momentary_flags_roundtrip():
    comp = {
        "id": "c2",
        "name": "Comp2",
        "data": {
            "tipo_consumo": "C.C. momentÃÂ¡neo",
            "potencia_w": 50.0,
        },
    }
    dm = _mk_dm_with_component(comp)
    ctrl = CCConsumptionController(dm)

    assert ctrl.set_momentary_flags("c2", False, 3) is True
    assert comp["data"].get("cc_mom_incluir") is False
    assert comp["data"].get("cc_mom_escenario") == 3

    items = iter_cc_items(dm.proyecto, get_model_gabinetes(dm))
    item = next((it for it in items if it.comp_id == "c2"), None)
    assert item is not None
    assert item.mom_incluir is False
    assert item.mom_escenario == 3
