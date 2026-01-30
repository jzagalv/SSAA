# -*- coding: utf-8 -*-
"""storage/project_schema.py

Funciones puras para normalizar estructuras de proyecto.

Objetivo:
- Mantener la lógica de "forma" del JSON fuera de DataModel para facilitar
  pruebas, migraciones y evolución del esquema.
- Este módulo NO depende de PyQt.

Nota:
- Estas funciones están alineadas con el comportamiento histórico del proyecto
  (copiadas desde DataModel). Evita cambios funcionales.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict


def normalize_sala_entry(sala: Any) -> Dict[str, str]:
    """Normaliza una entrada de sala a dict {"tag": ..., "nombre": ...}."""
    if isinstance(sala, (tuple, list)) and len(sala) >= 2:
        tag = sala[0] or ""
        nombre = sala[1] or ""
        return {"tag": tag, "nombre": nombre}
    if isinstance(sala, dict):
        return {
            "tag": sala.get("tag", "") or "",
            "nombre": sala.get("nombre", "") or "",
        }
    return {"tag": "", "nombre": ""}


def normalize_component_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza el dict 'data' de un componente de gabinete."""
    d: Dict[str, Any] = dict(data or {})
    d.setdefault("name", d.get("name", ""))  # opcional, espejo de 'base'
    d.setdefault("marca", "")
    d.setdefault("modelo", "")

    # compatibilidad: potencia_cc o potencia -> potencia_w
    if "potencia_w" not in d:
        if "potencia_cc" in d:
            d["potencia_w"] = d.get("potencia_cc", None)
        elif "potencia" in d:
            d["potencia_w"] = d.get("potencia", None)
        else:
            d["potencia_w"] = None

    d.setdefault("potencia_va", None)
    d.setdefault("usar_va", False)
    d.setdefault("tipo_consumo", "")
    d.setdefault("fase", "1F")
    d.setdefault("origen", "Genérico")

    # campos de alimentación
    d.setdefault("alimentador", d.get("alimentador", ""))
    d.setdefault("feed_ca_no_esencial", d.get("feed_ca_no_esencial", False))
    d.setdefault("feed_tablero_padre_ca_noes", d.get("feed_tablero_padre_ca_noes", ""))
    d.setdefault("tag", d.get("tag", ""))

    # C.C.
    d.setdefault("cc_perm_pct_custom", None)
    d.setdefault("cc_mom_incluir", True)
    d.setdefault("cc_mom_escenario", 1)
    d.setdefault("cc_aleatorio_sel", False)

    return d


def norm_pos(v: Any) -> Dict[str, float]:
    """Normaliza posición a {x,y}."""
    if isinstance(v, dict):
        x = v.get("x", 0.0)
        y = v.get("y", 0.0)
    elif isinstance(v, (list, tuple)) and len(v) >= 2:
        x, y = v[0], v[1]
    else:
        x, y = 0.0, 0.0
    try:
        x = float(x)
    except Exception:
        x = 0.0
    try:
        y = float(y)
    except Exception:
        y = 0.0
    return {"x": x, "y": y}


def norm_size(v: Any, default_w: float = 260.0, default_h: float = 120.0) -> Dict[str, float]:
    """Normaliza tamaño a {w,h}."""
    if isinstance(v, dict):
        w = v.get("w", default_w)
        h = v.get("h", default_h)
    elif isinstance(v, (list, tuple)) and len(v) >= 2:
        w, h = v[0], v[1]
    else:
        w, h = default_w, default_h
    try:
        w = float(w)
    except Exception:
        w = default_w
    try:
        h = float(h)
    except Exception:
        h = default_h
    if w <= 0:
        w = default_w
    if h <= 0:
        h = default_h
    return {"w": w, "h": h}




def normalize_cabinet_entry(gab: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza un gabinete a la estructura unificada."""
    g: Dict[str, Any] = dict(gab or {})
    g.setdefault("id", "")
    if not str(g.get("id", "")):
        g["id"] = uuid.uuid4().hex
    g.setdefault("is_board", False)
    g.setdefault("is_energy_source", False)
    g.setdefault("tag", "")
    g.setdefault("nombre", "")
    g.setdefault("sala", "")

    comps = g.get("components", [])
    if not isinstance(comps, list):
        comps = []

    norm_comps = []
    for c in comps:
        c = dict(c or {})
        c.setdefault("id", "")
        if not str(c.get("id", "")).strip():
            c["id"] = uuid.uuid4().hex

        c.setdefault("base", c.get("base", ""))
        c.setdefault("name", c.get("name", c.get("base", "")))

        c["pos"] = norm_pos(c.get("pos", None))
        c["size"] = norm_size(c.get("size", None))
        c["data"] = normalize_component_data(c.get("data", {}))
        norm_comps.append(c)

    g["components"] = norm_comps
    return g
