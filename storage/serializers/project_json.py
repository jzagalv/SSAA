# -*- coding: utf-8 -*-
"""Project serializer (schema v3 contract)."""
from __future__ import annotations

from typing import Any, Dict

from domain.models.project import Project, Installations, Cabinet
from storage.schema import PROJECT_VERSION
from storage.project_schema import normalize_cabinet_entry
from domain.contracts.cc_schema import SCHEMA_VERSION


def from_dict(data: Dict[str, Any]) -> Project:
    """Build Project from a dict assumed to be upgraded/normalized."""
    meta = data.get("_meta", {}) if isinstance(data.get("_meta", {}), dict) else {}
    proyecto = data.get("proyecto", {}) if isinstance(data.get("proyecto", {}), dict) else {}
    calculated = proyecto.get("calculated")
    if not isinstance(calculated, dict):
        calculated = {}
        proyecto["calculated"] = calculated

    library_links = meta.get("library_links", {}) if isinstance(meta.get("library_links", {}), dict) else {}

    ins = data.get("instalaciones", {}) if isinstance(data.get("instalaciones", {}), dict) else {}
    ubicaciones = list(ins.get("ubicaciones", []) or [])
    gab_raw = ins.get("gabinetes", [])
    if not isinstance(gab_raw, list):
        gab_raw = []
    gab_norm = [normalize_cabinet_entry(g) for g in gab_raw]
    cabinets = [Cabinet.from_dict(g) for g in gab_norm]

    installations = Installations(cabinets=cabinets, ubicaciones=ubicaciones)
    installations.sync_views()

    return Project(
        meta=meta,
        proyecto_dict=proyecto,
        installations=installations,
        calculated=calculated,
        library_links=library_links,
    )


def to_dict(project: Project) -> Dict[str, Any]:
    """Serialize Project to dict (same shape as legacy to_project_dict)."""
    project.sync_views()
    gab_dicts = [normalize_cabinet_entry(cab.raw) for cab in project.installations.cabinets]
    meta = dict(project.meta or {})
    meta["version"] = PROJECT_VERSION
    meta["schema_version"] = SCHEMA_VERSION
    meta["library_links"] = dict(project.library_links or {})

    return {
        "_meta": meta,
        "proyecto": dict(project.proyecto_dict or {}),
        "instalaciones": {
            "ubicaciones": list(project.installations.ubicaciones or []),
            "gabinetes": gab_dicts,
        },
        "componentes": {},
    }
