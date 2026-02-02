# -*- coding: utf-8 -*-
from __future__ import annotations

from data_model import DataModel


def test_ssot_identity_after_apply_project_dict():
    dm = DataModel()
    payload = {
        "_meta": {"version": 4},
        "proyecto": {},
        "instalaciones": {
            "ubicaciones": [],
            "gabinetes": [{"id": "g1", "tag": "G1", "components": []}],
        },
    }
    dm.from_dict(payload)
    assert id(dm.gabinetes) == id(dm.instalaciones["gabinetes"])
    assert id(dm.salas) == id(dm.instalaciones["ubicaciones"])
