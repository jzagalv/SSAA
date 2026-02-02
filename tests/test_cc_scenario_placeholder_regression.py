# -*- coding: utf-8 -*-
"""Regression tests for CC scenario placeholders (PyQt-free)."""
from __future__ import annotations

from dataclasses import dataclass, field

from screens.cc_consumption.utils import resolve_scenario_desc
from storage.project_serialization import apply_project_dict
from storage.schema import PROJECT_VERSION
from domain.contracts.cc_schema import SCHEMA_VERSION


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


def test_resolve_scenario_desc_prefers_db_over_placeholder():
    assert resolve_scenario_desc(1, "Escenario 1", "87B") == "87B"


def test_cc_escenarios_not_forced_to_placeholders_on_load():
    payload = {
        "_meta": {
            "version": PROJECT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "project_folder": "",
            "project_filename": "reg",
            "library_links": {},
        },
        "proyecto": {
            "cc_escenarios": {"1": "87B", "2": "55 2"},
            "cc_num_escenarios": 2,
        },
        "instalaciones": {"gabinetes": [], "ubicaciones": []},
        "componentes": {"gabinetes": []},
    }

    m = _DummyModel()
    apply_project_dict(m, payload)

    esc = m.proyecto.get("cc_escenarios", {})
    assert esc.get("1") == "87B"
    assert esc.get("2") == "55 2"
    for v in esc.values():
        assert not str(v).startswith("Escenario ")
