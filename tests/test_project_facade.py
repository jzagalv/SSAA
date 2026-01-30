# -*- coding: utf-8 -*-
"""Unit tests for ProjectFacade.

These tests are intentionally PyQt-free.
"""

from __future__ import annotations


from domain.project_facade import ProjectFacade
from core.keys import ProjectKeys as K


def test_facade_ensures_topology_layer_defaults():
    proy = {}
    f = ProjectFacade(proy)

    layer = f.ensure_ssaa_topology_layer("CA_ES")
    assert isinstance(layer, dict)
    assert layer["nodes"] == []
    assert layer["edges"] == []
    assert layer["used_feeders"] == []

    # Stored under the canonical key
    assert K.SSAA_TOPOLOGY_LAYERS in proy
    assert "CA_ES" in proy[K.SSAA_TOPOLOGY_LAYERS]


def test_facade_cc_scenarios_roundtrip_and_update():
    proy = {
        K.CC_SCENARIOS: {"B1": "Base"},
    }
    f = ProjectFacade(proy)

    assert f.get_cc_scenarios()["B1"] == "Base"
    f.update_cc_scenario_desc("B2", "Respaldo")
    assert f.get_cc_scenarios()["B2"] == "Respaldo"

    # Should persist as a plain dict
    assert isinstance(proy[K.CC_SCENARIOS], dict)
