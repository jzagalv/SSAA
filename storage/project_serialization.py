# -*- coding: utf-8 -*-
"""storage/project_serialization.py

Serialización/deserialización del estado del proyecto.

Este módulo NO depende de PyQt.

Nota: opera sobre un objeto tipo DataModel (duck-typing) para evitar
importar el modelo y generar acoplamientos/ciclos.
"""

from __future__ import annotations

import os
from copy import deepcopy

from storage.schema import PROJECT_VERSION
from storage.migrations import upgrade_project_dict
from storage.project_schema import normalize_cabinet_entry
from storage.project_paths import norm_project_path


def to_project_dict(model) -> dict:
    """Convierte el estado del modelo a dict serializable."""
    # Mantener compatibilidad: el modelo usa aliases legacy (salas/gabinetes)
    if hasattr(model, "_sync_aliases_in"):
        model._sync_aliases_in()

    salas_norm = list(getattr(model, "instalaciones", {}).get("ubicaciones", []))
    gabinetes = getattr(model, "instalaciones", {}).get("gabinetes", [])
    gab_norm = [normalize_cabinet_entry(g) for g in gabinetes]

    comp_gabs = [
        {"tag": g.get("tag", ""), "components": deepcopy(g.get("components", []))}
        for g in gab_norm
    ]

    library_paths = getattr(model, "library_paths", {}) or {}

    return {
        "_meta": {
            "project_folder": getattr(model, "project_folder", "") or "",
            "project_filename": getattr(model, "project_filename", "") or "",
            "version": PROJECT_VERSION,
            "library_links": {
                "consumos": library_paths.get("consumos", ""),
                "materiales": library_paths.get("materiales", ""),
            },
        },
        "proyecto": dict(getattr(model, "proyecto", {}) or {}),
        "instalaciones": {
            "ubicaciones": salas_norm,
            "gabinetes": gab_norm,
        },
        "componentes": {
            "gabinetes": comp_gabs,
        },
    }


def apply_project_dict(model, data: dict, file_path: str = "") -> None:
    """Carga un dict (posiblemente legacy) dentro del modelo."""
    data = upgrade_project_dict(data, to_version=PROJECT_VERSION)

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

    if hasattr(model, "proyecto") and isinstance(model.proyecto, dict):
        model.proyecto.update(data.get("proyecto", {}) or {})

    ins = data.get("instalaciones", {}) if isinstance(data.get("instalaciones", {}), dict) else {}
    if hasattr(model, "instalaciones") and isinstance(model.instalaciones, dict):
        model.instalaciones["ubicaciones"] = list(ins.get("ubicaciones", []) or [])
        model.instalaciones["gabinetes"] = list(ins.get("gabinetes", []) or [])

    # componentes: vista derivada (no fuente de verdad)
    if hasattr(model, "componentes") and isinstance(model.componentes, dict):
        model.componentes["gabinetes"] = [
            {"tag": g.get("tag", ""), "components": deepcopy(g.get("components", []))}
            for g in model.instalaciones.get("gabinetes", [])
        ]

    if hasattr(model, "_sync_aliases_out"):
        model._sync_aliases_out()

    model.dirty = False
