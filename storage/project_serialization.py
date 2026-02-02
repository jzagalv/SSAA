# -*- coding: utf-8 -*-
"""storage/project_serialization.py

Serialización/deserialización del estado del proyecto.

Este módulo NO depende de PyQt.

Nota: opera sobre un objeto tipo DataModel (duck-typing) para evitar
importar el modelo y generar acoplamientos/ciclos.
"""

from __future__ import annotations

import os

from storage.schema import PROJECT_VERSION
from storage.migrations import upgrade_project_dict
from storage.project_schema import normalize_cabinet_entry
from storage.project_paths import norm_project_path
from domain.contracts.cc_schema import (
    SCHEMA_VERSION,
    normalize_project,
    ensure_cc_scenarios,
    ensure_calculated_cc,
    validate_project,
)
from storage.serializers.project_json import from_dict as project_from_dict
from storage.serializers.project_json import to_dict as project_to_dict


def to_project_dict(model) -> dict:
    """Convierte el estado del modelo a dict serializable."""
    if getattr(model, "project_model", None) is not None:
        data = project_to_dict(model.project_model)
        proj = data.get("proyecto")
        if isinstance(proj, dict):
            proj = dict(proj)
            proj.pop("cc_results", None)
            data["proyecto"] = proj
        meta = data.get("_meta", {}) if isinstance(data.get("_meta", {}), dict) else {}
        if not meta.get("project_folder") and getattr(model, "project_folder", ""):
            meta["project_folder"] = getattr(model, "project_folder", "") or ""
        if not meta.get("project_filename") and getattr(model, "project_filename", ""):
            meta["project_filename"] = getattr(model, "project_filename", "") or ""
        data["_meta"] = meta
        return data
    # Mantener compatibilidad: el modelo usa aliases legacy (salas/gabinetes)
    if hasattr(model, "_sync_aliases_in"):
        model._sync_aliases_in()

    salas_norm = list(getattr(model, "instalaciones", {}).get("ubicaciones", []))
    gabinetes = getattr(model, "instalaciones", {}).get("gabinetes", [])
    gab_norm = [normalize_cabinet_entry(g) for g in gabinetes]

    library_paths = getattr(model, "library_paths", {}) or {}

    proj_dict = dict(getattr(model, "proyecto", {}) or {})
    proj_dict.pop("cc_results", None)
    return {
        "_meta": {
            "project_folder": getattr(model, "project_folder", "") or "",
            "project_filename": getattr(model, "project_filename", "") or "",
            "version": PROJECT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "library_links": {
                "consumos": library_paths.get("consumos", ""),
                "materiales": library_paths.get("materiales", ""),
            },
        },
        "proyecto": proj_dict,
        "instalaciones": {
            "ubicaciones": salas_norm,
            "gabinetes": gab_norm,
        },
        "componentes": {},
    }


def apply_project_dict(model, data: dict, file_path: str = "") -> None:
    """Carga un dict (posiblemente legacy) dentro del modelo."""
    if isinstance(data.get("_derived", None), dict):
        data["_derived"].pop("cc_results", None)
    data = upgrade_project_dict(data, to_version=PROJECT_VERSION)
    proj_model = project_from_dict(data)
    if hasattr(model, "set_project"):
        model.set_project(proj_model)
    else:
        setattr(model, "project_model", proj_model)
    proj = data.get("proyecto", {})
    if isinstance(proj, dict):
        normalize_project(proj)
        try:
            n_esc = int(proj.get("cc_num_escenarios", 1) or 1)
        except Exception:
            n_esc = 1
        ensure_cc_scenarios(proj, n_esc)
        ensure_calculated_cc(proj)
        issues = validate_project(proj)
        if issues:
            import logging
            logging.getLogger(__name__).debug("Project contract validation: %s", issues)

    meta = data.get("_meta", {}) if isinstance(data.get("_meta", {}), dict) else {}
    model.project_folder = meta.get("project_folder", "") or ""
    model.project_filename = meta.get("project_filename", "") or ""

    # Ruta de archivo
    model.file_path = norm_project_path(model.project_folder, model.project_filename)
    model.file_name = os.path.basename(model.file_path) if model.file_path else ""

    # Librerías: solo referencias (NO cargar automáticamente)
    links = meta.get("library_links", {}) if isinstance(meta.get("library_links", {}), dict) else {}
    if hasattr(model, "library_paths"):
        model.library_paths["consumos"] = str(links.get("consumos", "") or "")
        model.library_paths["materiales"] = str(links.get("materiales", "") or "")

    if not hasattr(model, "set_project"):
        proj_dict = data.get("proyecto", {}) if isinstance(data.get("proyecto", {}), dict) else {}
        if hasattr(model, "proyecto") and isinstance(model.proyecto, dict):
            model.proyecto.clear()
            model.proyecto.update(proj_dict)
        elif hasattr(model, "proyecto"):
            model.proyecto = proj_dict

        ins = data.get("instalaciones", {}) if isinstance(data.get("instalaciones", {}), dict) else {}
        ubicaciones = ins.get("ubicaciones", []) if isinstance(ins.get("ubicaciones", []), list) else []
        gabinetes = ins.get("gabinetes", []) if isinstance(ins.get("gabinetes", []), list) else []

        if hasattr(model, "instalaciones") and isinstance(model.instalaciones, dict):
            model.instalaciones["ubicaciones"] = ubicaciones
            model.instalaciones["gabinetes"] = gabinetes
        elif hasattr(model, "instalaciones"):
            model.instalaciones = {"ubicaciones": ubicaciones, "gabinetes": gabinetes}

        if hasattr(model, "ubicaciones"):
            model.ubicaciones = ubicaciones
        if hasattr(model, "salas"):
            model.salas = ubicaciones
        if hasattr(model, "gabinetes"):
            model.gabinetes = gabinetes

        # componentes: vista derivada (no fuente de verdad)
        if hasattr(model, "componentes") and isinstance(model.componentes, dict):
            model.componentes["gabinetes"] = [
                {"tag": g.get("tag", ""), "components": g.get("components", [])}
                for g in gabinetes
            ]

    if hasattr(model, "_sync_aliases_out"):
        model._sync_aliases_out()

    model.dirty = False
