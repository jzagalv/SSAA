# -*- coding: utf-8 -*-
"""
services/normalize.py

Etapa 1 (refactor): normalización de datos cargados desde JSON para evitar
inconsistencias de tipos (p.ej. números guardados como strings) y asegurar
defaults mínimos.

Este módulo NO depende de PyQt. Se usa desde DataModel al cargar proyectos.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import os

from domain.parse import to_float, is_blank

_NUM_KEYS_FLOAT = {
    # Proyecto
    "tension_nominal",
    "frecuencia_hz",
    "max_voltaje_cc",
    "min_voltaje_cc",
    "tiempo_autonomia",
    "porcentaje_utilizacion",
    "tension_flotacion_celda",
    "v_max",
    "v_min",

    # Factores banco (si existen)
    "bb_k2_temp",
    "bb_margen_diseno",
    "bb_factor_envejec",

    # Cargador
    "charger_t_rec_h",
    "charger_k_loss",
    "charger_k_alt",
    "charger_k_temp",
    "charger_k_seg",
    "charger_eff",

    # Política comercial
    "commercial_step_ah",
    "commercial_step_a",
}

_NUM_KEYS_INT = {
    "num_celdas_usuario",
}

_BOOL_KEYS_PROY = {
    "cc_usar_pct_global",
}

# Campos típicos en componente->data
_COMP_FLOAT_KEYS = {
    "potencia_w",
    "potencia_va",
    "cc_perm_pct_custom",
}

_COMP_INT_KEYS = {
    "cc_mom_escenario",
}

_COMP_BOOL_KEYS = {
    "usar_va",
    "cc_aleatorio_sel",
    "cc_mom_incluir",
}

def _to_int(value: Any) -> Optional[int]:
    """
    Convierte a int.
    - None / "" -> None (no ingresado)
    - "3" -> 3
    - "3,0" -> 3
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    s = str(value).strip()
    if not s:
        return None

    try:
        return int(float(s.replace(",", ".")))
    except ValueError:
        return None


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in {"true", "1", "yes", "y", "si", "sí"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return default


def normalize_meta(meta: Dict[str, Any], file_path: Optional[str] = None) -> Dict[str, Any]:
    """Asegura que el meta no rompa portabilidad. Si viene file_path, preferimos su carpeta."""
    meta = dict(meta or {})
    if file_path:
        folder = os.path.dirname(os.path.abspath(file_path))
        meta["project_folder"] = folder
        # Si no hay filename lógico, tomamos el stem del archivo
        if not meta.get("project_filename"):
            base = os.path.splitext(os.path.basename(file_path))[0]
            meta["project_filename"] = base
    return meta


def normalize_proyecto(proy: Dict[str, Any]) -> Dict[str, Any]:
    proy = dict(proy or {})

    # floats: "" / None quedan como None
    for k in _NUM_KEYS_FLOAT:
        if k in proy:
            proy[k] = to_float(proy.get(k))

    # ints: "" / None quedan como None
    for k in _NUM_KEYS_INT:
        if k in proy:
            proy[k] = _to_int(proy.get(k))

    # bools
    for k in _BOOL_KEYS_PROY:
        if k in proy:
            proy[k] = _to_bool(
                proy.get(k),
                default=True if k == "cc_usar_pct_global" else False
            )

    # perfil de cargas: normalizamos números cuando es posible.
    # Si no es numérico (por compatibilidad), se conserva el valor original.
    def _normalize_perfil_rows(perfil_rows: Any) -> None:
        if not isinstance(perfil_rows, list):
            return
        for row in perfil_rows:
            if not isinstance(row, dict):
                continue
            for kk in ("p", "i", "t_inicio", "duracion"):
                if kk in row and not is_blank(row.get(kk)):
                    val = row.get(kk)
                    f = to_float(val)
                    row[kk] = f if f is not None else val

    _normalize_perfil_rows(proy.get("perfil_cargas", None))
    bc = proy.get("bank_charger", None)
    if isinstance(bc, dict):
        _normalize_perfil_rows(bc.get("perfil_cargas", None))

    # Defaults de políticas comerciales
    proy.setdefault("commercial_step_ah", 10.0)
    proy.setdefault("commercial_step_a", 10.0)
    proy.setdefault("charger_rounding_mode", "nearest")

    return proy


def _normalize_salas(salas: Any) -> List[Any]:
    if not isinstance(salas, list):
        return []
    out = []
    for s in salas:
        if isinstance(s, (list, tuple)) and len(s) >= 2:
            out.append([str(s[0]), str(s[1])])
        else:
            # compat: si venía como string
            name = str(s)
            out.append([name, name])
    return out


def normalize_component_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza data del componente.
    - potencia_w / potencia_va: Optional[float] (None si no ingresado)
    - usar_va define cuál se interpreta después en cálculo/validación
    """
    data = dict(data or {})

    # floats (permiten None)
    for k in _COMP_FLOAT_KEYS:
        if k in data:
            data[k] = to_float(data.get(k))

    # ints
    for k in _COMP_INT_KEYS:
        if k in data:
            iv = _to_int(data.get(k))
            data[k] = max(1, iv) if iv is not None else 1  # UI-friendly

    # bools
    for k in _COMP_BOOL_KEYS:
        if k in data:
            default = True if k == "cc_mom_incluir" else False
            data[k] = _to_bool(data.get(k), default=default)

    # Limpieza opcional: si usar_va es True y potencia_va viene vacío, no inventar 0.
    # (Esto NO valida, solo deja limpio. La validación real va en domain/calculators.)
    usar_va = data.get("usar_va", False)
    if usar_va:
        # si está usando VA, W puede quedar None
        pass
    else:
        # si está usando W, VA puede quedar None
        pass

    return data

def _norm_pos(value: Any) -> Dict[str, float]:
    # Acepta {"x":..,"y":..} o [x,y] o (x,y)
    if isinstance(value, dict):
        x = value.get("x", 0)
        y = value.get("y", 0)
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        x, y = value[0], value[1]
    else:
        x, y = 0, 0

    try:
        x = float(x)
    except Exception:
        x = 0.0
    try:
        y = float(y)
    except Exception:
        y = 0.0

    return {"x": x, "y": y}


def _norm_size(value: Any, default_w: float = 160, default_h: float = 60) -> Dict[str, float]:
    # Acepta {"w":..,"h":..} o [w,h]
    if isinstance(value, dict):
        w = value.get("w", default_w)
        h = value.get("h", default_h)
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        w, h = value[0], value[1]
    else:
        w, h = default_w, default_h

    try:
        w = float(w)
    except Exception:
        w = float(default_w)
    try:
        h = float(h)
    except Exception:
        h = float(default_h)

    # Sanidad mínima: tamaños no negativos / cero
    if w <= 0:
        w = float(default_w)
    if h <= 0:
        h = float(default_h)

    return {"w": w, "h": h}


def normalize_gabinetes(gabinetes: Any) -> List[Dict[str, Any]]:
    if not isinstance(gabinetes, list):
        return []
    out: List[Dict[str, Any]] = []
    for g in gabinetes:
        if not isinstance(g, dict):
            continue
        gg = dict(g)
        comps = gg.get("components", []) or []
        if not isinstance(comps, list):
            comps = []
        norm_comps = []
        for c in comps:
            if not isinstance(c, dict):
                continue
            cc = dict(c)

            # pos/size: aceptar lista o dict, guardar siempre dict estándar
            cc["pos"] = _norm_pos(cc.get("pos"))
            cc["size"] = _norm_size(cc.get("size"))

            cc["data"] = normalize_component_data(cc.get("data", {}))
            norm_comps.append(cc)
        gg["components"] = norm_comps
        out.append(gg)
    return out


def normalize_installations(ins: Dict[str, Any]) -> Dict[str, Any]:
    ins = dict(ins or {})
    ins["salas"] = _normalize_salas(ins.get("salas", []))
    ins["gabinetes"] = normalize_gabinetes(ins.get("gabinetes", []))
    return ins


def normalize_project_dict(data: Dict[str, Any], file_path: Optional[str] = None) -> Dict[str, Any]:
    """Normaliza un dict completo de proyecto (estructura que viene del JSON)."""
    data = dict(data or {})
    data["_meta"] = normalize_meta(data.get("_meta", {}), file_path=file_path)
    data["proyecto"] = normalize_proyecto(data.get("proyecto", {}))
    data["instalaciones"] = normalize_installations(data.get("instalaciones", {}))

    # componentes paralelos (si existen)
    comp = data.get("componentes", {})
    if isinstance(comp, dict) and "gabinetes" in comp:
        # no tocamos su estructura, sólo aseguramos lista
        if not isinstance(comp.get("gabinetes"), list):
            comp["gabinetes"] = []
        data["componentes"] = comp

    return data
