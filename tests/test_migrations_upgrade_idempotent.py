# -*- coding: utf-8 -*-
"""Tests for storage.migrations.upgrade_project_dict.

These tests should remain PyQt-free and validate that:
- legacy payloads can be upgraded to the current schema version
- upgrades are idempotent (running twice does not keep changing data)
"""

from __future__ import annotations

from copy import deepcopy

from storage.migrations import upgrade_project_dict
from storage.schema import PROJECT_VERSION
from core.keys import ProjectKeys as K


def test_upgrade_from_v1_produces_v4_and_is_idempotent():
    legacy_v1 = {
        "_meta": {"version": 1},
        "proyecto": {
            "frecuencia": 50,
            # legacy designer topology key may exist
            K.SSAA_TOPOLOGY: {"nodes": [], "edges": []},
        },
        # legacy top-level lists
        "salas": [["S1", "Sala 1"]],
        "gabinetes": [
            {"tag": "G1", "sala": "S1 - Sala 1", "components": []},
        ],
    }

    upgraded_1 = upgrade_project_dict(deepcopy(legacy_v1), to_version=PROJECT_VERSION)
    assert upgraded_1.get("_meta", {}).get("version") == PROJECT_VERSION
    assert isinstance(upgraded_1.get("instalaciones"), dict)
    assert isinstance(upgraded_1["instalaciones"].get("ubicaciones"), list)
    assert isinstance(upgraded_1["instalaciones"].get("gabinetes"), list)
    assert len(upgraded_1["instalaciones"]["gabinetes"]) == 1
    assert upgraded_1["instalaciones"]["gabinetes"][0].get("id")

    # Ensure we have a topology layers dict even if empty, and it is a dict.
    topo_layers = (upgraded_1.get("proyecto", {}) or {}).get(K.SSAA_TOPOLOGY_LAYERS, {})
    assert isinstance(topo_layers, dict)

    # Idempotency: upgrading a v4 payload again should not change the result.
    upgraded_2 = upgrade_project_dict(deepcopy(upgraded_1), to_version=PROJECT_VERSION)
    assert upgraded_2 == upgraded_1
