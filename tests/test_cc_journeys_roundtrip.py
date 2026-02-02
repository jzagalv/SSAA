# -*- coding: utf-8 -*-
"""Journey-style tests for CC roundtrip persistence (PyQt-free)."""
from __future__ import annotations

from dataclasses import dataclass, field

from storage.project_serialization import apply_project_dict, to_project_dict
from storage.schema import PROJECT_VERSION
from domain.contracts.cc_schema import SCHEMA_VERSION
from domain.cc_consumption import iter_cc_items, get_model_gabinetes


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

    def _sync_aliases_in(self):
        return None

    def _sync_aliases_out(self):
        return None


def _make_project_dict() -> dict:
    return {
        "_meta": {
            "version": PROJECT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "project_folder": "",
            "project_filename": "journey",
            "library_links": {},
        },
        "proyecto": {
            "cc_num_escenarios": 2,
            "cc_escenarios": {"1": "87B", "2": "55 2"},
            "cc_scenarios_summary": [],
            "calculated": {"cc": {"summary": {}, "scenarios_totals": {}}},
        },
        "instalaciones": {
            "ubicaciones": [],
            "gabinetes": [
                {
                    "id": "g1",
                    "tag": "G1",
                    "nombre": "Gab1",
                    "components": [
                        {
                            "id": "c1",
                            "name": "Carga Mom",
                            "data": {
                                "tipo_consumo": "C.C. momentÃÂ¡neo",
                                "potencia_w": 120.0,
                                "cc_mom_incluir": True,
                                "cc_mom_escenario": 1,
                            },
                        },
                        {
                            "id": "c2",
                            "name": "Carga Ale",
                            "data": {
                                "tipo_consumo": "C.C. aleatorio",
                                "potencia_w": 80.0,
                                "cc_aleatorio_sel": True,
                            },
                        },
                    ],
                }
            ],
        },
        "componentes": {"gabinetes": []},
    }


def test_cc_roundtrip_preserves_scenarios_and_flags():
    payload = _make_project_dict()

    m1 = _DummyModel()
    apply_project_dict(m1, payload)

    saved = to_project_dict(m1)

    m2 = _DummyModel()
    apply_project_dict(m2, saved)

    assert m2.proyecto.get("cc_escenarios", {}).get("1") == "87B"
    assert m2.proyecto.get("cc_escenarios", {}).get("2") == "55 2"

    # Placeholders should not be persisted
    for v in (m2.proyecto.get("cc_escenarios", {}) or {}).values():
        assert not str(v).startswith("Escenario ")

    # Aleatorio selection persists
    gabs = m2.instalaciones.get("gabinetes", [])
    assert gabs
    comps = gabs[0].get("components", [])
    comp_sel = next((c for c in comps if c.get("id") == "c2"), None)
    assert comp_sel is not None
    assert bool((comp_sel.get("data", {}) or {}).get("cc_aleatorio_sel")) is True

    # CC items not empty
    items = iter_cc_items(m2.proyecto, get_model_gabinetes(m2))
    assert len(items) >= 1
