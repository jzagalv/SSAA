# -*- coding: utf-8 -*-
import json
from pathlib import Path

import pytest

from storage.migrations import upgrade_project_dict
from storage.schema import PROJECT_VERSION
from domain.project_facade import ProjectFacade
from core.keys import ProjectKeys as K


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "fname",
    [
        "sample_project.ssaa",
        "sample_project_modern.ssaa",
        "sample_project_edge.ssaa",
    ],
)
def test_smoke_upgrade_sample_project_files(fname: str):
    sample_file = Path(__file__).parent / "data" / fname
    data = _load(sample_file)

    upgraded = upgrade_project_dict(data, to_version=PROJECT_VERSION)

    # version bump / normalized (some schemas store version in _meta)
    meta = upgraded.get("_meta", {}) if isinstance(upgraded.get("_meta", {}), dict) else {}
    assert meta.get("version") == PROJECT_VERSION or upgraded.get("project_version") == PROJECT_VERSION

    proy = upgraded.get("proyecto", {})
    if isinstance(proy, dict) and proy:
        # frecuencia should be normalized to frecuencia_hz (int/float)
        assert "frecuencia_hz" in proy

    # cabinets normalized with ids (either via instalaciones or legacy merge)
    ins = upgraded.get("instalaciones", {})
    if isinstance(ins, dict):
        gabs = ins.get("gabinetes", [])
    else:
        gabs = []
    assert isinstance(gabs, list)
    if gabs:
        assert all(isinstance(g.get("id", ""), str) and g.get("id") for g in gabs)

    # topology layers must be a dict after upgrade (even if malformed in source)
    f = ProjectFacade(upgraded)
    f.ensure_ssaa_topology_layer("MAIN")
    assert K.SSAA_TOPOLOGY_LAYERS in upgraded
    layers = upgraded[K.SSAA_TOPOLOGY_LAYERS]
    assert isinstance(layers, dict)
    assert "MAIN" in layers
