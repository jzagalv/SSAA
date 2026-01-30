
# -*- coding: utf-8 -*-
"""services/load_tables_engine.py

Construcción de cuadros de carga (CA y CC) a partir de:
- Topología (proyecto[ProjectKeys.SSAA_TOPOLOGY_LAYERS][workspace]) para resolver cascadas
- Datos de gabinetes y componentes (data_model.gabinetes) para obtener potencias

Este módulo NO depende de PyQt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import math

from core.keys import ProjectKeys as K

def _cdata(c: Dict) -> Dict:
    """Retorna el dict de datos del componente.

    En esta app, los 'components' de un gabinete suelen venir desde el diseñador con forma:
      {id, base, name, pos, size, data:{...campos reales...}}
    Para compatibilidad, si no existe 'data', devolvemos el mismo dict.
    """
    if isinstance(c, dict):
        d = c.get("data")
        if isinstance(d, dict):
            return d
    return c if isinstance(c, dict) else {}

def _cget(c: Dict, key: str, default=None):
    d = _cdata(c)
    return d.get(key, default)

def _cname(c: Dict) -> str:
    d = _cdata(c)
    return str(d.get("tag") or d.get("name") or c.get("name") or c.get("base") or "").strip()


# ------------------------------ helpers ------------------------------

def to_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def _tipo_is_ca_esencial(tipo: str) -> bool:
    return (tipo or "").strip().upper() == "C.A. ESENCIAL"


def _tipo_is_ca_noes(tipo: str) -> bool:
    return (tipo or "").strip().upper() == "C.A. NO ESENCIAL"


def _tipo_is_cc(tipo: str) -> bool:
    t = (tipo or "").strip().upper()
    return t.startswith("C.C.")


def _tipo_is_cc_permanente(tipo: str) -> bool:
    return (tipo or "").strip().upper() == "C.C. PERMANENTE"


def _tipo_is_cc_momentaneo_or_aleatorio(tipo: str) -> bool:
    t = (tipo or "").strip().upper()
    return t in ("C.C. MOMENTÁNEO", "C.C. MOMENTANEO", "C.C. ALEATORIO")


def _phase_kind_from_components(components: List[Dict]) -> str:
    """Devuelve '3F' si hay algún componente 3F, si no '1F'."""
    for c in components or []:
        fase = str(_cget(c, "fase", "1F") or "1F").strip().upper()
        if "3" in fase:
            return "3F"
    return "1F"


def _calc_i_ac(p_w: float, *, fase: str, v_mono: Optional[float], v_tri: Optional[float], fp: float = 0.9) -> Tuple[float, float, float]:
    """Retorna (IR, IS, IT) estimadas. Si no hay tensión, retorna (0,0,0)."""
    p_w = max(0.0, float(p_w))
    fp = fp if fp and fp > 0 else 1.0
    fase = (fase or "1F").upper()

    if "3" in fase:
        v = v_tri
        if not v:
            return (0.0, 0.0, 0.0)
        i = p_w / (math.sqrt(3.0) * float(v) * fp) if v else 0.0
        return (i, i, i)
    else:
        v = v_mono
        if not v:
            return (0.0, 0.0, 0.0)
        i = p_w / (float(v) * fp) if v else 0.0
        # Sin datos de fase R/S/T, asignamos por defecto a R.
        return (i, 0.0, 0.0)


def _calc_i_dc(p_w: float, v_dc: Optional[float]) -> float:
    if not v_dc:
        return 0.0
    p_w = max(0.0, float(p_w))
    return p_w / float(v_dc)


def _parse_feeder_key(key: str) -> Optional[Tuple[str, str, Optional[int], str]]:
    """
    Soporta ambos formatos:
      - legacy:  scope:gi:ci:req   (gi es índice int)
      - nuevo:   scope:gid:ci:req  (gid es UUID string del gabinete)

    Retorna: (scope, gabinete_ref, ci_int, req)
      - gabinete_ref: puede ser "27" (legacy) o "550e8400-e29b-41d4-a716-..." (uuid)
    """
    try:
        parts = str(key).split(":")
        if len(parts) != 4:
            return None
        scope = parts[0].strip()
        gabinete_ref = parts[1].strip()          # <-- int o uuid, lo dejamos como string
        ci = parts[2].strip()
        ci_int = None if ci == "None" else int(ci)
        req = parts[3].strip()
        if not scope or not gabinete_ref or not req:
            return None
        return scope, gabinete_ref, ci_int, req
    except Exception:
        return None

def _resolve_gabinete(gabinetes: List[Dict], gabinete_ref: str) -> Optional[Dict]:
    """
    Resuelve el gabinete desde gabinete_ref:
      - si es dígito => índice legacy
      - si no => UUID (campo gabinetes[].id)
    """
    if not gabinete_ref:
        return None

    # legacy: índice
    if gabinete_ref.isdigit():
        gi = int(gabinete_ref)
        if 0 <= gi < len(gabinetes):
            return gabinetes[gi] or None
        return None

    # nuevo: UUID
    for g in gabinetes:
        if not isinstance(g, dict):
            continue
        if str(g.get("id") or "") == gabinete_ref:
            return g
    return None

def _topo_get_layer(proyecto: Dict, workspace: str) -> Optional[Dict]:
    layers = proyecto.get(K.SSAA_TOPOLOGY_LAYERS)
    if not isinstance(layers, dict):
        return None
    topo = layers.get(workspace)
    if not isinstance(topo, dict):
        return None
    topo.setdefault("nodes", [])
    topo.setdefault("edges", [])
    return topo


def _build_adj(edges: List[Dict]) -> Dict[str, List[str]]:
    adj: Dict[str, List[str]] = {}
    for e in edges or []:
        src = str(e.get("src", ""))
        dst = str(e.get("dst", ""))
        if not src or not dst:
            continue
        adj.setdefault(src, []).append(dst)
    return adj


def _reachable_nodes(topo: Dict, start_id: str) -> List[Dict]:
    nodes = topo.get("nodes", []) or []
    edges = topo.get("edges", []) or []
    node_by_id = {str(n.get("id")): n for n in nodes if isinstance(n, dict)}
    adj = _build_adj(edges)

    seen = set()
    out = []
    stack = [start_id]
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        n = node_by_id.get(nid)
        if n:
            out.append(n)
        for nxt in adj.get(nid, []):
            if nxt not in seen:
                stack.append(nxt)
    return out


def _subfeeder_groups(topo: Dict, board_id: str) -> List[Dict[str, Any]]:
    """Agrupa nodos por subalimentador.

    Definición:
      - Cada salida directa del tablero (hijo directo) se interpreta como un *subalimentador*.
      - Si un subalimentador alimenta otras cargas en cascada (aguas abajo), esas cargas se
        consideran parte del mismo subalimentador (paralelo sobre el mismo circuito).

    Retorna una lista de grupos:
      [{"root_id": <hijo_directo>, "node_ids": [<ids_subarbol_incluye_root>]}, ...]
    """
    board_id = str(board_id or "")
    if not board_id:
        return []

    nodes = topo.get("nodes", []) or []
    edges = topo.get("edges", []) or []
    node_ids = {str(n.get("id")) for n in nodes if isinstance(n, dict) and n.get("id") is not None}
    adj = _build_adj(edges)

    first_hops = [x for x in (adj.get(board_id, []) or []) if str(x) in node_ids]
    groups: List[Dict[str, Any]] = []
    used: set = set()

    for root in first_hops:
        root = str(root)
        if not root:
            continue

        # BFS/DFS desde root
        stack = [root]
        seen: set = set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for nxt in adj.get(cur, []) or []:
                nxt = str(nxt)
                if nxt and nxt not in seen:
                    stack.append(nxt)

        # Evitar solapamientos si el grafo tiene reconvergencias
        node_list = [nid for nid in seen if nid not in used]
        used.update(node_list)

        groups.append({"root_id": root, "node_ids": node_list})

    return groups


def _ac_power_for_node(ln: Dict, *, req: str, gabinetes: List[Dict]) -> Tuple[float, str, str]:
    """Calcula potencia W para un nodo CARGA y devuelve (p_w, fase_kind, ubicacion).

    req: 'CA_ES' o 'CA_NOES'
    """
    meta = dict(ln.get("meta", {}) or {})
    fk = meta.get("feeder_key")
    if not fk:
        return (0.0, "1F", "")
    parsed = _parse_feeder_key(fk)
    if not parsed:
        return (0.0, "1F", "")
    scope, gref, ci, req_code = parsed
    if req_code != req:
        return (0.0, "1F", "")

    g = _resolve_gabinete(gabinetes, gref)
    if not g:
        return (0.0, "1F", "")
    ubic = str(g.get("sala", "") or "").strip()

    # componentes asociados
    if scope == "gabinete":
        comps = list(g.get("components", []) or [])
    else:
        allc = list(g.get("components", []) or [])
        if ci is None or ci < 0 or ci >= len(allc):
            return (0.0, "1F", ubic)
        comps = [allc[ci]]

    if req == "CA_ES":
        comps_f = [c for c in comps if _tipo_is_ca_esencial(str(_cget(c, "tipo_consumo", "")))]
    else:
        comps_f = [c for c in comps if _tipo_is_ca_noes(str(_cget(c, "tipo_consumo", "")))]

    # Potencia: preferimos lo que viene del diseñador (node.p_w) si está disponible.
    p_node = to_float(ln.get("p_w"), 0.0)
    p_total = p_node if p_node > 0 else sum(to_float(_cget(c, "potencia_w"), 0.0) for c in comps_f)
    if p_total <= 0:
        return (0.0, "1F", ubic)

    fase_kind = _phase_kind_from_components(comps_f)
    return (float(p_total), fase_kind, ubic)


def _cc_powers_for_node(ln: Dict, *, req: str, gabinetes: List[Dict]) -> Tuple[float, float, str]:
    """Calcula (p_perm_w, p_mom_w, ubicacion) para un nodo CC en la capa req ('CC_B1'/'CC_B2')."""
    meta = dict(ln.get("meta", {}) or {})
    fk = meta.get("feeder_key")
    if not fk:
        return (0.0, 0.0, "")
    parsed = _parse_feeder_key(fk)
    if not parsed:
        return (0.0, 0.0, "")
    scope, gref, ci, req_code = parsed
    if req_code != req:
        return (0.0, 0.0, "")
    g = _resolve_gabinete(gabinetes, gref)
    if not g:
        return (0.0, 0.0, "")
    ubic = str(g.get("sala", "") or "").strip()

    if scope == "gabinete":
        comps = list(g.get("components", []) or [])
    else:
        allc = list(g.get("components", []) or [])
        if ci is None or ci < 0 or ci >= len(allc):
            return (0.0, 0.0, ubic)
        comps = [allc[ci]]

    comps_cc = [c for c in comps if _tipo_is_cc(str(_cget(c, "tipo_consumo", "")))]
    if not comps_cc:
        return (0.0, 0.0, ubic)

    # Preferencia: si el diseñador ya entregó valores por nodo, se usan.
    p_perm_meta = to_float(meta.get("p_perm_w"), 0.0)
    p_mom_meta = to_float(meta.get("p_mom_w"), 0.0)
    if p_perm_meta > 0 or p_mom_meta > 0:
        return (p_perm_meta, p_mom_meta, ubic)

    p_perm = sum(to_float(_cget(c, "potencia_w"), 0.0)
                 for c in comps_cc
                 if _tipo_is_cc_permanente(str(_cget(c, "tipo_consumo", ""))))
    p_mom = sum(to_float(_cget(c, "potencia_w"), 0.0)
                for c in comps_cc
                if _tipo_is_cc_momentaneo_or_aleatorio(str(_cget(c, "tipo_consumo", ""))))
    return (p_perm, p_mom, ubic)


# ------------------------------ public API ------------------------------

@dataclass
class ACRow:
    node_id: str
    descripcion: str
    tag: str
    ubicacion: str
    n_itm: str
    capacidad_itm: str
    cap_dif: str
    fases: str
    p_total_w: float
    fp: float
    fd: float
    consumo_va: float
    i_r: float
    i_s: float
    i_t: float


@dataclass
class CCRow:
    node_id: str
    barra: str
    descripcion: str
    tag: str
    ubicacion: str
    n_circuito: str
    n_conductores: str
    calibre: str
    tipo: str
    n_itm: str
    capacidad_itm: str
    p_perm_w: float
    i_perm_a: float
    p_mom_w: float
    i_mom_a: float
    obs: str


def build_ac_table(data_model, *, workspace: str, board_node_id: str) -> List[ACRow]:
    """Construye tabla CA para un workspace CA_ES o CA_NOES."""
    p = getattr(data_model, "proyecto", {}) or {}
    topo = _topo_get_layer(p, workspace)
    if not topo or not board_node_id:
        return []

    v_mono = to_float(p.get("tension_monofasica"), 0.0) or None
    v_tri = to_float(p.get("tension_trifasica"), 0.0) or None

    gabinetes = getattr(data_model, "gabinetes", None) or []

    rows: List[ACRow] = []
    req = "CA_ES" if workspace == "CA_ES" else "CA_NOES"

    # Cada fila = salida directa del tablero (subalimentador). Si hay cascada, se suma.
    groups = _subfeeder_groups(topo, board_node_id)
    nodes_by_id = {str(n.get("id")): n for n in (topo.get("nodes") or []) if isinstance(n, dict) and n.get("id") is not None}

    for g in groups:
        root_id = str(g.get("root_id") or "")
        if not root_id:
            continue
        root_node = nodes_by_id.get(root_id)
        if not root_node or str(root_node.get("kind", "")).upper() != "CARGA":
            continue

        # nodos CARGA dentro del subárbol (incluye root si es CARGA)
        group_nodes = []
        for nid in (g.get("node_ids") or []):
            n = nodes_by_id.get(str(nid))
            if not n:
                continue
            if str(n.get("id")) == str(board_node_id):
                continue
            if str(n.get("kind", "")).upper() != "CARGA":
                continue
            group_nodes.append(n)

        if not group_nodes:
            continue

        # Suma de potencias del subalimentador
        p_sum = 0.0
        fase_kind = "1F"
        ubic = ""
        for ln in group_nodes:
            p_w, fk, ubic_ln = _ac_power_for_node(ln, req=req, gabinetes=gabinetes)
            if p_w > 0:
                p_sum += p_w
            if "3" in str(fk):
                fase_kind = "3F"
            if not ubic and ubic_ln:
                ubic = ubic_ln

        if p_sum <= 0:
            continue

        meta_root = dict(root_node.get("meta", {}) or {})

        fp = 0.90
        fd = 1.00
        consumo_va = p_sum / fp if fp else p_sum
        ir, is_, it_ = _calc_i_ac(p_sum, fase=fase_kind, v_mono=v_mono, v_tri=v_tri, fp=fp)

        rows.append(ACRow(
            node_id=str(root_node.get("id") or ""),
            descripcion=str(meta_root.get("desc") or "").strip(),
            tag=str(meta_root.get("tag") or "").strip(),
            ubicacion=ubic,
            n_itm=str(meta_root.get("load") or "").strip() or "-",
            capacidad_itm="-",
            cap_dif="-",
            fases=("R-S-T" if "3" in fase_kind else "R"),
            p_total_w=p_sum,
            fp=fp,
            fd=fd,
            consumo_va=consumo_va,
            i_r=ir,
            i_s=is_,
            i_t=it_,
        ))

    return rows


def build_cc_table(data_model, *, workspace: str, board_node_id: str) -> List[CCRow]:
    """Construye tabla CC para un workspace CC_B1 o CC_B2."""
    p = getattr(data_model, "proyecto", {}) or {}
    topo = _topo_get_layer(p, workspace)
    if not topo or not board_node_id:
        return []

    v_dc = to_float(p.get("tension_nominal"), 0.0) or None

    gabinetes = getattr(data_model, "gabinetes", None) or []
    req = "CC_B1" if workspace == "CC_B1" else "CC_B2"
    barra = "Barra 1" if req == "CC_B1" else "Barra 2"

    rows: List[CCRow] = []

    # Cada fila = salida directa del tablero (subalimentador). Si hay cascada, se suma.
    groups = _subfeeder_groups(topo, board_node_id)
    nodes_by_id = {str(n.get("id")): n for n in (topo.get("nodes") or []) if isinstance(n, dict) and n.get("id") is not None}

    for g in groups:
        root_id = str(g.get("root_id") or "")
        if not root_id:
            continue
        root_node = nodes_by_id.get(root_id)
        if not root_node or str(root_node.get("kind", "")).upper() != "CARGA":
            continue

        group_nodes = []
        for nid in (g.get("node_ids") or []):
            n = nodes_by_id.get(str(nid))
            if not n:
                continue
            if str(n.get("id")) == str(board_node_id):
                continue
            if str(n.get("kind", "")).upper() != "CARGA":
                continue
            group_nodes.append(n)

        if not group_nodes:
            continue

        p_perm_sum = 0.0
        p_mom_sum = 0.0
        ubic = ""
        for ln in group_nodes:
            pp, pm, ubic_ln = _cc_powers_for_node(ln, req=req, gabinetes=gabinetes)
            p_perm_sum += max(0.0, float(pp))
            p_mom_sum += max(0.0, float(pm))
            if not ubic and ubic_ln:
                ubic = ubic_ln

        if p_perm_sum <= 0 and p_mom_sum <= 0:
            continue

        meta_root = dict(root_node.get("meta", {}) or {})
        i_perm = _calc_i_dc(p_perm_sum, v_dc)
        i_mom = _calc_i_dc(p_mom_sum, v_dc)

        rows.append(CCRow(
            node_id=str(root_node.get("id") or ""),
            barra=barra,
            descripcion=str(meta_root.get("desc") or "").strip(),
            tag=str(meta_root.get("tag") or "").strip(),
            ubicacion=ubic,
            n_circuito="-",
            n_conductores="-",
            calibre="-",
            tipo="-",
            n_itm=str(meta_root.get("load") or "").strip() or "-",
            capacidad_itm="-",
            p_perm_w=p_perm_sum,
            i_perm_a=i_perm,
            p_mom_w=p_mom_sum,
            i_mom_a=i_mom,
            obs="",
        ))

    return rows


def list_board_nodes(data_model, *, workspace: str) -> List[Tuple[str, str]]:
    """Retorna [(node_id, label)] de tableros disponibles en un workspace.

    Criterio (robusto):
    - Un gabinete es "tablero" si instalaciones.gabinetes[].is_board == True
    - En topología, el nodo debe tener meta.gabinete_id (inyectado en upgrade_dict).
      Si no lo tiene, intentamos resolver por feeder_key legado (gabinete:<gi>:...).
    """
    p = getattr(data_model, "proyecto", {}) or {}
    topo = _topo_get_layer(p, workspace)
    if not topo:
        return []

    gabinetes = getattr(data_model, "gabinetes", None) or []
    board_ids = {str(g.get("id")): g for g in gabinetes if bool(g.get("is_board", False))}
    if not board_ids:
        return []

    # helper: legacy feeder_key -> gabinete_id
    def _gid_from_feeder_key(fk: str) -> Optional[str]:
        try:
            if not fk.startswith("gabinete:"):
                return None
            parts = fk.split(":")
            if len(parts) != 4:
                return None
            gref = parts[1].strip()

            # legacy índice
            if gref.isdigit():
                gi = int(gref)
                if 0 <= gi < len(gabinetes):
                    return str(gabinetes[gi].get("id") or "")

            # nuevo UUID
            for g in gabinetes:
                if str(g.get("id") or "") == gref:
                    return str(g.get("id") or "")

        except Exception:
            return None
        return None

    out: List[Tuple[str, str]] = []
    for n in topo.get("nodes", []) or []:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id", ""))
        meta = dict(n.get("meta", {}) or {})
        gid = str(meta.get("gabinete_id") or "")
        if not gid:
            fk = str(meta.get("feeder_key") or n.get("feeder_key") or "")
            gid = _gid_from_feeder_key(fk) or ""
            if gid and isinstance(meta, dict):
                meta["gabinete_id"] = gid
                n["meta"] = meta

        if gid not in board_ids:
            continue

        g = board_ids[gid]
        tag = str(g.get("tag", "")).strip()
        nombre = str(g.get("nombre", "")).strip()
        label = f"{tag} — {nombre}".strip(" —")
        out.append((nid, label))

    # orden estable por etiqueta
    out.sort(key=lambda x: x[1].lower())
    return out

