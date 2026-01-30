# -*- coding: utf-8 -*-
"""Smoke tests for storage.project_serialization.

Validates that a minimal model can be serialized and then loaded back
without PyQt, and that the upgrade path produces a stable schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from storage.project_serialization import to_project_dict, apply_project_dict
from storage.schema import PROJECT_VERSION
from core.keys import ProjectKeys as K


@dataclass
class _DummyModel:
    project_folder: str = ""
    project_filename: str = ""
    file_path: str = ""
    file_name: str = ""
    dirty: bool = False
    proyecto: dict = field(default_factory=dict)
    instalaciones: dict = field(default_factory=lambda: {"ubicaciones": [], "gabinetes": []})
    componentes: dict = field(default_factory=lambda: {"gabinetes": []})
    library_paths: dict = field(default_factory=lambda: {"consumos": "", "materiales": ""})

    # DataModel compatibility hooks (no-ops here)
    def _sync_aliases_in(self):
        return None

    def _sync_aliases_out(self):
        return None


def test_serialization_roundtrip_smoke():
    m = _DummyModel(project_folder="/tmp", project_filename="demo")
    m.proyecto[K.UTILIZATION_PCT_GLOBAL] = 40
    m.proyecto[K.SSAA_TOPOLOGY_LAYERS] = {"CA_ES": {"nodes": [], "edges": [], "used_feeders": []}}
    m.instalaciones["ubicaciones"] = [{"id": "u1", "tag": "S1", "nombre": "Sala"}]
    m.instalaciones["gabinetes"] = [{"id": "g1", "tag": "G1", "components": []}]

    payload = to_project_dict(m)
    assert payload.get("_meta", {}).get("version") == PROJECT_VERSION

    m2 = _DummyModel()
    apply_project_dict(m2, payload)

    # Roundtrip keeps core structures
    assert m2.proyecto.get(K.UTILIZATION_PCT_GLOBAL) == 40
    assert isinstance(m2.proyecto.get(K.SSAA_TOPOLOGY_LAYERS), dict)
    assert len(m2.instalaciones.get("gabinetes", [])) == 1
    assert m2.dirty is False