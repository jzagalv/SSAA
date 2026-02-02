# -*- coding: utf-8 -*-
"""Domain models for SSOT runtime graph."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Component:
    id: str
    tag: str
    data: Dict[str, Any]
    raw: Dict[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Component":
        raw = data if isinstance(data, dict) else {}
        comp_id = str(raw.get("id", "") or "").strip()
        comp_data = raw.get("data")
        if not isinstance(comp_data, dict):
            comp_data = {}
            raw["data"] = comp_data
        tag = str(comp_data.get("tag", raw.get("tag", "")) or "")
        return cls(id=comp_id, tag=tag, data=comp_data, raw=raw)


@dataclass
class Cabinet:
    id: str
    tag: str
    nombre: str
    ubicacion_id: str
    components: List[Component]
    raw: Dict[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Cabinet":
        raw = data if isinstance(data, dict) else {}
        cab_id = str(raw.get("id", "") or "").strip()
        tag = str(raw.get("tag", "") or "").strip()
        nombre = str(raw.get("nombre", raw.get("descripcion", "")) or "").strip()
        ubicacion_id = str(raw.get("ubicacion_id", "") or "").strip()
        comps_raw = raw.get("components")
        if not isinstance(comps_raw, list):
            comps_raw = []
            raw["components"] = comps_raw
        components = [Component.from_dict(c) for c in comps_raw if isinstance(c, dict)]
        return cls(
            id=cab_id,
            tag=tag,
            nombre=nombre,
            ubicacion_id=ubicacion_id,
            components=components,
            raw=raw,
        )


@dataclass
class Installations:
    cabinets: List[Cabinet]
    ubicaciones: List[Dict[str, Any]]
    cabinets_view: List[Dict[str, Any]] = field(default_factory=list, repr=False)

    def sync_views(self) -> None:
        """Keep cabinets_view as a stable list of cabinet dicts."""
        self.cabinets_view[:] = [cab.raw for cab in self.cabinets]

    def sync_from_view(self) -> None:
        """Rebuild Cabinet objects from the dict view list."""
        self.cabinets = [Cabinet.from_dict(c) for c in self.cabinets_view if isinstance(c, dict)]


@dataclass
class Project:
    meta: Dict[str, Any]
    proyecto_dict: Dict[str, Any]
    installations: Installations
    calculated: Dict[str, Any]
    library_links: Dict[str, Any]

    def sync_views(self) -> None:
        # Ensure both lists are in sync (view -> objects -> view)
        self.installations.sync_from_view()
        self.installations.sync_views()
