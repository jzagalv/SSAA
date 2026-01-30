# -*- coding: utf-8 -*-
"""domain/ssaa_topology.py

Modelos de topología SS/AA (independiente de UI).

El diseñador gráfico (PyQt5) persiste nodos y enlaces en
``proyecto['ssaa_topology']``. Para mantener separación de responsabilidades,
las estructuras de datos y su serialización viven aquí (sin dependencias Qt).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


def to_float(v, default: float = 0.0) -> float:
    """Convierte a float aceptando coma decimal. Devuelve ``default`` si falla."""
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return float(default)


@dataclass
class TopoNode:
    id: str
    kind: str  # TGCA/TDCA/TDAyF/TGCC/TDCC/CARGA/CARGADOR
    name: str
    pos: Tuple[float, float]
    size: Tuple[float, float] = (220.0, 90.0)
    dc_system: str = "B1"  # aplica a nodos CC (y algunos mixtos)
    p_w: float = 0.0       # potencia (si corresponde)
    meta: Dict | None = None  # metadatos libres (origen, feed_type, barra, etc.)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "pos": {"x": float(self.pos[0]), "y": float(self.pos[1])},
            "size": {"w": float(self.size[0]), "h": float(self.size[1])},
            "dc_system": self.dc_system,
            "p_w": float(self.p_w or 0.0),
            "meta": dict(self.meta or {}),
        }

    @staticmethod
    def from_dict(d: Dict) -> "TopoNode":
        pos = d.get("pos", {}) or {}
        size = d.get("size", {}) or {}
        return TopoNode(
            id=str(d.get("id")),
            kind=str(d.get("kind")),
            name=str(d.get("name", "")),
            pos=(float(pos.get("x", 0.0)), float(pos.get("y", 0.0))),
            size=(float(size.get("w", 220.0)), float(size.get("h", 90.0))),
            dc_system=str(d.get("dc_system", "B1")),
            p_w=to_float(d.get("p_w", 0.0), 0.0),
            meta=dict(d.get("meta", {}) or {}),
        )


@dataclass
class TopoEdge:
    id: str
    src: str
    dst: str
    circuit: str  # CA o CC
    dc_system: str = "B1"  # aplica a CC
    meta: Dict | None = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "src": self.src,
            "dst": self.dst,
            "circuit": self.circuit,
            "dc_system": self.dc_system,
            "meta": dict(self.meta or {}),
        }

    @staticmethod
    def from_dict(d: Dict) -> "TopoEdge":
        return TopoEdge(
            id=str(d.get("id")),
            src=str(d.get("src")),
            dst=str(d.get("dst")),
            circuit=str(d.get("circuit", "CA")),
            dc_system=str(d.get("dc_system", "B1")),
            meta=dict(d.get("meta", {}) or {}),
        )
