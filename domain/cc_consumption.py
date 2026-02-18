# -*- coding: utf-8 -*-
"""
domain/cc_consumption.py

Dominio: cálculo de consumos C.C. desde gabinetes/componentes.
- No depende de PyQt.
- Lee estructura tipo DataModel:
    instalaciones["gabinetes"] -> [{ "components": [ { "data": {...} } ] }]
- Considera:
    - C.C. permanente con % global o % custom
    - C.C. aleatorio (si seleccionado)
    - C.C. momentáneo por escenarios, con inclusión
    - Potencia "momentánea" derivada de permanentes (100% - pct)

Este módulo está pensado para ser consumido por la UI (screen.py) sin lógica eléctrica dentro.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional
import hashlib
import json

from .parse import to_float

# -------------------------
# Cast / helpers
# -------------------------

def _as_float(v: Any) -> Optional[float]:
    return to_float(v, default=None)


def _as_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(float(s.replace(",", ".")))
    except Exception:
        return None


def _clamp(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def _effective_power_w(data: Dict[str, Any]) -> float:
    """
    Devuelve potencia efectiva en W:
    - si usar_va=True y potencia_va>0 -> usa potencia_va
    - si no -> potencia_w
    """
    usar_va = bool(data.get("usar_va", False))
    pw = to_float(data.get("potencia_w")) or 0.0
    pva = to_float(data.get("potencia_va")) or 0.0
    if usar_va and pva > 0:
        return float(pva)
    return float(pw)


def _normalize_comp_data(data: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(data or {})
    d.setdefault("tag", "")
    d.setdefault("marca", "")
    d.setdefault("modelo", "")
    if "potencia_w" not in d:
        if "potencia_cc" in d:
            d["potencia_w"] = d.get("potencia_cc", "")
        elif "potencia" in d:
            d["potencia_w"] = d.get("potencia", "")
        else:
            d["potencia_w"] = ""
    d.setdefault("potencia_va", "")
    d.setdefault("usar_va", False)
    d.setdefault("tipo_consumo", "")
    d.setdefault("fase", "1F")
    d.setdefault("origen", "Genérico")
    return d


def momentary_state_signature(rows: List[Dict[str, Any]], vmin: float, n_scenarios: int) -> str:
    """Deterministic signature for momentary rows + context."""
    items: List[Tuple[str, bool, int, float, float]] = []
    for row in rows or []:
        comp_id = str(row.get("comp_id") or row.get("id") or "")
        incluir = bool(row.get("incluir", False))
        try:
            esc = int(row.get("escenario") or 1)
        except Exception:
            esc = 1
        try:
            p_eff = float(row.get("p_efectiva_w") or row.get("p_eff") or row.get("p_w") or 0.0)
        except Exception:
            p_eff = 0.0
        try:
            i_a = float(row.get("i_a") or row.get("i_eff") or 0.0)
        except Exception:
            i_a = 0.0
        items.append((comp_id, incluir, esc, round(p_eff, 6), round(i_a, 6)))

    items.sort(key=lambda x: x[0])
    payload = {
        "vmin": float(vmin or 0.0),
        "n_scenarios": int(n_scenarios or 0),
        "rows": items,
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


# -------------------------
# Proyecto: Vnom/Vmin/%global
# -------------------------

def get_vcc_nominal(proyecto: Dict[str, Any], default: float = 125.0) -> float:
    v = to_float((proyecto or {}).get("tension_nominal")) or default
    return float(v) if v > 0 else float(default)


def get_vcc_for_currents(proyecto: Dict[str, Any], default_nom: float = 125.0) -> float:
    """
    Nota importante:
    - Aunque exista proyecto["v_min"], preferimos recalcular desde
      tensión_nominal y min_voltaje_cc cuando esos datos están disponibles.
      Esto evita quedar “pegados” a un v_min antiguo si el usuario cambia
      la tensión nominal o el % mínimo en la pestaña Proyecto y aún no ha
      pasado por la pantalla Banco y cargador.

    Prioridad:
    1) Vnom*(1-min_voltaje_cc/100) si hay datos
    2) proyecto["v_min"] en volt [V]
    3) Vnom
    """
    p = proyecto or {}

    v_nom = to_float(p.get("tension_nominal")) or 0.0
    pct_min = to_float(p.get("min_voltaje_cc")) or 0.0
    if v_nom > 0.0 and pct_min > 0.0:
        v_calc = v_nom * (1.0 - pct_min / 100.0)
        if v_calc > 0:
            return float(v_calc)

    v_min = to_float(p.get("v_min"))
    if v_min is not None and v_min > 0:
        return float(v_min)

    return get_vcc_nominal(p, default=default_nom)


def get_pct_global(proyecto: Dict[str, Any], default: float = 100.0) -> float:
    pct = to_float((proyecto or {}).get("porcentaje_utilizacion"))
    if pct is None:
        pct = default
    return float(_clamp(float(pct), 0.0, 100.0))


def get_usar_pct_global(proyecto: Dict[str, Any], default: bool = True) -> bool:
    return bool((proyecto or {}).get("cc_usar_pct_global", default))


def get_num_escenarios(proyecto: Dict[str, Any], default: int = 1) -> int:
    n = _as_int((proyecto or {}).get("cc_num_escenarios"))
    if n is None:
        n = default
    if n < 1:
        n = 1
    if n > 20:
        n = 20
    return int(n)


def get_escenarios_desc(proyecto: Dict[str, Any]) -> Dict[str, str]:
    """Obtiene descripciones de escenarios de forma robusta.

    Fuente preferida:
      - proyecto['cc_escenarios']  (dict { "1": "desc", ... })

    Fallback legacy:
      - proyecto['cc_scenarios_summary'] como lista de dicts (cuando existe 'desc'/'descripcion')
        Ejemplos históricos:
          [{"escenario": 1, "desc": "..."}, ...]
          [{"n": 1, "descripcion": "..."}, ...]
    """
    proj = proyecto or {}
    esc = proj.get("cc_escenarios", {}) or {}
    out: Dict[str, str] = {}
    if isinstance(esc, dict):
        for k, v in esc.items():
            out[str(k)] = ("" if v is None else str(v))

    # Fallback: summary list (legacy)
    if not out:
        legacy = proj.get("cc_scenarios_summary")
        if isinstance(legacy, list):
            for row in legacy:
                if not isinstance(row, dict):
                    continue
                k = row.get("escenario", row.get("n", row.get("id")))
                try:
                    k = str(int(k))
                except Exception:
                    continue
                desc = row.get("desc", row.get("descripcion", row.get("description", "")))
                if desc is None:
                    desc = ""
                out[k] = str(desc)
    return out


# -------------------------
# Gabinetes / iteración
# -------------------------

def get_model_gabinetes(data_model: Any) -> List[Dict[str, Any]]:
    """
    Obtiene gabinetes desde data_model de forma tolerante:
    - data_model.instalaciones["gabinetes"] si existe
    - fallback data_model.gabinetes
    """
    def _count_components(gabs: List[Dict[str, Any]]) -> int:
        total = 0
        for gab in gabs or []:
            if not isinstance(gab, dict):
                continue
            comps = gab.get("components", []) or []
            total += len(comps)
        return total

    instalaciones = getattr(data_model, "instalaciones", {}) or {}
    gab_inst = instalaciones.get("gabinetes", None)
    gab_alias = getattr(data_model, "gabinetes", None)

    if isinstance(gab_inst, list) and isinstance(gab_alias, list):
        comp_inst = _count_components(gab_inst)
        comp_alias = _count_components(gab_alias)
        if comp_alias > comp_inst:
            return gab_alias
        if comp_inst > comp_alias:
            return gab_inst
        return gab_alias

    if isinstance(gab_inst, list):
        return gab_inst
    if isinstance(gab_alias, list):
        return gab_alias
    return []


@dataclass(frozen=True)
class CCItem:
    gab_tag: str
    gab_nombre: str
    comp_id: str
    tag_comp: str
    desc: str
    p_eff: float
    i_eff: float
    tipo: str
    # flags persistidos
    mom_incluir: bool = True
    mom_escenario: int = 1
    ale_sel: bool = False
    # acceso opcional al dict original
    comp: Optional[Dict[str, Any]] = None


def iter_cc_items(
    proyecto: Dict[str, Any],
    gabinetes: List[Dict[str, Any]],
) -> List[CCItem]:
    """
    Devuelve lista de items C.C. (permanente/momentáneo/aleatorio)
    con potencia efectiva y corriente calculada con Vmin.
    """
    vcc = get_vcc_for_currents(proyecto)
    out: List[CCItem] = []

    for gab in gabinetes or []:
        gab_tag = str(gab.get("tag", "") or "")
        gab_nombre = str(gab.get("nombre", "") or "")

        for comp in (gab.get("components", []) or []):
            data = _normalize_comp_data(comp.get("data", {}) or {})
            tipo = str(data.get("tipo_consumo", "") or "").strip()
            if not tipo.startswith("C.C."):
                continue

            p_eff = _effective_power_w(data)
            if p_eff <= 0:
                continue

            i_eff = (p_eff / vcc) if vcc > 0 else 0.0

            nombre_comp = comp.get("name") or comp.get("base") or ""
            tag_comp = data.get("tag", "") or nombre_comp

            comp_id = str(comp.get("id", "") or "").strip()

            mom_incluir = bool(data.get("cc_mom_incluir", True))
            mom_escenario = int(_as_int(data.get("cc_mom_escenario")) or 1)
            if mom_escenario < 1:
                mom_escenario = 1

            ale_sel = bool(data.get("cc_aleatorio_sel", False))

            out.append(
                CCItem(
                    gab_tag=gab_tag,
                    gab_nombre=gab_nombre,
                    comp_id=comp_id,
                    tag_comp=str(tag_comp or ""),
                    desc=str(nombre_comp or ""),
                    p_eff=float(p_eff),
                    i_eff=float(i_eff),
                    tipo=tipo,
                    mom_incluir=mom_incluir,
                    mom_escenario=mom_escenario,
                    ale_sel=ale_sel,
                    comp=comp,
                )
            )

    return out


def split_by_tipo(items: List[CCItem]) -> Tuple[List[CCItem], List[CCItem], List[CCItem]]:
    perm, mom, ale = [], [], []
    for it in items:
        if it.tipo == "C.C. permanente":
            perm.append(it)
        elif it.tipo == "C.C. momentáneo":
            mom.append(it)
        elif it.tipo == "C.C. aleatorio":
            ale.append(it)
    return perm, mom, ale


# -------------------------
# Permanentes: fila + totales
# -------------------------

def get_pct_for_permanent(
    proyecto: Dict[str, Any],
    comp_data: Dict[str, Any],
) -> float:
    """
    Decide el % para una carga permanente:
    - si cc_usar_pct_global=True -> porcentaje_utilizacion
    - si cc_usar_pct_global=False -> cc_perm_pct_custom si existe (puede ser 0), si no global
    """
    pct_global = get_pct_global(proyecto)
    usar_global = get_usar_pct_global(proyecto)

    if usar_global:
        return pct_global

    pct_custom = to_float((comp_data or {}).get("cc_perm_pct_custom"))
    if pct_custom is None:
        return pct_global

    # OJO: 0% es válido → NO filtrar por >0
    return float(_clamp(float(pct_custom), 0.0, 100.0))


@dataclass(frozen=True)
class PermanentRowCalc:
    p_total: float
    pct: float
    p_perm: float
    p_mom: float
    i_perm: float
    i_mom: float


def calc_permanent_row(p_total: float, pct: float, vmin: float) -> PermanentRowCalc:
    pct = _clamp(float(pct), 0.0, 100.0)
    p_total = float(p_total)

    p_perm = p_total * (pct / 100.0)
    p_mom = max(0.0, p_total * ((100.0 - pct) / 100.0))

    if vmin > 0:
        i_perm = p_perm / vmin
        i_mom = p_mom / vmin
    else:
        i_perm = 0.0
        i_mom = 0.0

    return PermanentRowCalc(
        p_total=p_total,
        pct=pct,
        p_perm=float(p_perm),
        p_mom=float(p_mom),
        i_perm=float(i_perm),
        i_mom=float(i_mom),
    )


def calc_permanent_totals(rows: List[PermanentRowCalc]) -> Dict[str, float]:
    tot = {"p_total": 0.0, "p_perm": 0.0, "p_mom": 0.0, "i_perm": 0.0, "i_mom": 0.0}
    for r in rows or []:
        tot["p_total"] += r.p_total
        tot["p_perm"] += r.p_perm
        tot["p_mom"] += r.p_mom
        tot["i_perm"] += r.i_perm
        tot["i_mom"] += r.i_mom
    return {k: float(v) for k, v in tot.items()}


# -------------------------
# Aleatorios: totales
# -------------------------

def calc_aleatory_totals(items: List[CCItem]) -> Dict[str, float]:
    p = 0.0
    i = 0.0
    for it in items or []:
        if it.tipo != "C.C. aleatorio":
            continue
        if bool(it.ale_sel):
            p += float(it.p_eff)
            i += float(it.i_eff)
    return {"p_total": float(p), "i_total": float(i)}


# -------------------------
# Momentáneos: resumen escenarios
# -------------------------

def _sanitize_esc(esc: int, n_esc: int) -> int:
    try:
        esc = int(esc or 1)
    except Exception:
        esc = 1
    if esc < 1:
        esc = 1
    if esc > n_esc:
        esc = 1
    return esc


def calc_momentary_summary(
    items: List[CCItem],
    n_esc: int,
    include_perm_derived: bool,
    proyecto: Dict[str, Any],
    vmin: float,
) -> Dict[int, Dict[str, float]]:
    """
    Suma por escenario:
      - C.C. momentáneo con mom_incluir=True y mom_escenario.
      - opcional: potencia momentánea derivada desde permanentes: p_eff*(100-pct)/100 al escenario 1.
    Retorna: {esc: {"p_total": W, "i_total": A}}
    """
    if vmin <= 0:
        vmin = 1.0

    n_esc = max(1, int(n_esc or 1))
    sum_p: Dict[int, float] = {k: 0.0 for k in range(1, n_esc + 1)}

    # 1) momentáneos explícitos
    for it in items or []:
        if it.tipo != "C.C. momentáneo":
            continue
        if not bool(it.mom_incluir):
            continue
        esc = _sanitize_esc(int(it.mom_escenario or 1), n_esc)
        sum_p[esc] += float(it.p_eff)

    # 2) momentáneo derivado de permanentes
    if include_perm_derived:
        p_mom_perm_total = 0.0
        for it in items or []:
            if it.tipo != "C.C. permanente":
                continue
            comp_data = (it.comp or {}).get("data", {}) or {}
            pct = get_pct_for_permanent(proyecto, comp_data)
            p_mom_perm_total += float(it.p_eff) * ((100.0 - pct) / 100.0)

        if p_mom_perm_total > 0:
            sum_p[1] = sum_p.get(1, 0.0) + float(p_mom_perm_total)

    out: Dict[int, Dict[str, float]] = {}
    for esc in range(1, n_esc + 1):
        p = float(sum_p.get(esc, 0.0))
        out[int(esc)] = {"p_total": p, "i_total": float(p / vmin)}
    return out


# =====================================================================================
# COMPATIBILIDAD: tus funciones originales (mismos nombres/firmas)
# =====================================================================================

def compute_cc_profile_totals(
    proyecto: Dict[str, Any],
    gabinetes: List[Dict[str, Any]],
) -> Tuple[float, float]:
    """
    Retorna:
        (p_perm_total_w, p_ale_total_w)

    - Permanentes:
        p_eff * pct/100 (pct global o custom si cc_usar_pct_global=False)
    - Aleatorios:
        si cc_aleatorio_sel=True -> suma completa p_eff
    """
    pct_global = get_pct_global(proyecto)
    usar_pct_global = get_usar_pct_global(proyecto)

    p_perm_total = 0.0
    p_ale_total = 0.0

    for cab in gabinetes or []:
        for comp in (cab.get("components", []) or []):
            data = _normalize_comp_data(comp.get("data", {}) or {})
            tipo = str(data.get("tipo_consumo", "") or "").strip()
            p_eff = _effective_power_w(data)
            if p_eff <= 0:
                continue

            if tipo == "C.C. permanente":
                pct = pct_global
                if not usar_pct_global:
                    pct_custom = to_float(data.get("cc_perm_pct_custom"))
                    if pct_custom is not None:  # ✅ permite 0%
                        pct = pct_custom
                pct = _clamp(float(pct), 0.0, 100.0)
                p_perm_total += p_eff * (pct / 100.0)

            elif tipo == "C.C. aleatorio":
                if bool(data.get("cc_aleatorio_sel", False)):
                    p_ale_total += p_eff

    return float(p_perm_total), float(p_ale_total)


def compute_momentary_from_permanents(
    proyecto: Dict[str, Any],
    gabinetes: List[Dict[str, Any]],
) -> float:
    """Potencia momentánea derivada desde consumos C.C. permanentes.

    Definición (consistente con pantalla C.C. y escenarios):
        p_mom = p_eff * ((100 - pct_utilizacion)/100)

    Donde pct_utilizacion proviene de:
    - porcentaje_utilizacion si cc_usar_pct_global=True
    - cc_perm_pct_custom (si existe, incluyendo 0) cuando cc_usar_pct_global=False
    """

    p_mom_perm_total = 0.0

    for cab in gabinetes or []:
        for comp in (cab.get("components", []) or []):
            data = _normalize_comp_data(comp.get("data", {}) or {})
            tipo = str(data.get("tipo_consumo", "") or "").strip()
            if tipo != "C.C. permanente":
                continue

            p_eff = _effective_power_w(data)
            if p_eff <= 0:
                continue

            pct = _pct_for_permanent(proyecto, data)
            pct = _clamp(float(pct), 0.0, 100.0)

            p_mom = p_eff * ((100.0 - pct) / 100.0)
            if p_mom > 0:
                p_mom_perm_total += p_mom

    return float(p_mom_perm_total)


def compute_momentary_scenarios(
    proyecto: Dict[str, Any],
    gabinetes: List[Dict[str, Any]],
    vmin: float,
) -> Dict[int, Dict[str, float]]:
    """Compute momentary totals per scenario honoring include-perm map."""
    if vmin <= 0:
        vmin = 1.0

    sum_p_selected: Dict[int, float] = {}
    max_esc = 1

    for cab in gabinetes or []:
        for comp in (cab.get("components", []) or []):
            data = _normalize_comp_data(comp.get("data", {}) or {})
            tipo = str(data.get("tipo_consumo", "") or "").strip()
            if tipo != "C.C. momentÃ¡neo":
                continue
            if not bool(data.get("cc_mom_incluir", True)):
                continue

            esc = _as_int(data.get("cc_mom_escenario")) or 1
            if esc < 1:
                esc = 1
            if esc > max_esc:
                max_esc = esc

            p_eff = _effective_power_w(data)
            if p_eff <= 0:
                continue

            sum_p_selected[esc] = sum_p_selected.get(esc, 0.0) + p_eff

    p_mom_perm_total = float(compute_momentary_from_permanents(proyecto, gabinetes) or 0.0)
    include_map_raw = (proyecto or {}).get("cc_mom_incl_perm", {})
    include_map: Dict[str, bool] = {}
    if isinstance(include_map_raw, dict):
        for key, raw in include_map_raw.items():
            k = str(key)
            if isinstance(raw, str):
                include_map[k] = raw.strip().casefold() in ("1", "true", "yes", "on")
            else:
                include_map[k] = bool(raw)
            try:
                k_int = int(k)
            except Exception:
                k_int = None
            if k_int is not None and k_int > max_esc:
                max_esc = k_int

    out: Dict[int, Dict[str, float]] = {}
    for esc in range(1, max_esc + 1):
        p_total = float(sum_p_selected.get(esc, 0.0))
        if p_mom_perm_total > 0.0 and bool(include_map.get(str(esc), False)):
            p_total += p_mom_perm_total
        out[int(esc)] = {"p_total": p_total, "i_total": float(p_total / vmin)}
    return out


def _pct_for_permanent(proyecto: Dict[str, Any], data: Dict[str, Any]) -> float:
    """
    Determina % utilización para un permanente:
    - si cc_usar_pct_global=True -> usa porcentaje_utilizacion
    - si cc_usar_pct_global=False -> usa cc_perm_pct_custom si existe (incluye 0), si no global
    """
    pct_global = to_float(proyecto.get("porcentaje_utilizacion"))
    if pct_global is None:
        pct_global = 100.0
    pct_global = max(0.0, min(100.0, float(pct_global)))

    usar_pct_global = bool(proyecto.get("cc_usar_pct_global", True))
    if usar_pct_global:
        return pct_global

    pct_custom = to_float(data.get("cc_perm_pct_custom"))
    if pct_custom is None:
        return pct_global

    pct_custom = max(0.0, min(100.0, float(pct_custom)))
    return pct_custom


def compute_cc_permanentes_totals(
    proyecto: Dict[str, Any],
    gabinetes: List[Dict[str, Any]],
    vmin: float,
) -> Dict[str, float]:
    """
    Totales para la sección de Permanentes (los que muestra la UI):
      - p_total: suma de p_eff de permanentes
      - p_perm : suma de p_eff * pct/100
      - p_mom  : p_total - p_perm
      - i_perm : p_perm / vmin
      - i_mom  : p_mom / vmin

    Nota: 'p_mom' aquí es la parte NO utilizada (100-pct), tal como tu tabla.
    """
    if vmin <= 0:
        vmin = 1.0

    p_total = 0.0
    p_perm = 0.0

    for cab in gabinetes or []:
        for comp in (cab.get("components", []) or []):
            data = comp.get("data", {}) or {}
            tipo = str(data.get("tipo_consumo", "") or "").strip()
            if tipo != "C.C. permanente":
                continue

            p_eff = _effective_power_w(data)
            if p_eff <= 0:
                continue

            pct = _pct_for_permanent(proyecto, data)

            p_total += p_eff
            p_perm += p_eff * (pct / 100.0)

    p_mom_total = max(0.0, float(p_total - p_perm))
    i_mom_total = float(p_mom_total / vmin)

    return {
        "p_total": float(p_total),
        "p_perm": float(p_perm),
        "p_mom": float(p_mom_total),
        "i_perm": float(p_perm / vmin),
        "i_mom": float(i_mom_total),
    }

def compute_momentary_scenarios_full(
    proyecto: Dict[str, Any],
    gabinetes: List[Dict[str, Any]],
    vmin: float,
    n_escenarios: int,
) -> Dict[int, Dict[str, float]]:
    """
    Wrapper: entrega escenarios 1..n_escenarios siempre, aunque no haya cargas.
    Usa compute_momentary_scenarios (incluye cola derivada de permanentes al escenario objetivo).
    """
    try:
        n = int(n_escenarios or 1)
    except Exception:
        n = 1
    n = max(1, min(20, n))

    base = compute_momentary_scenarios(proyecto, gabinetes, vmin)
    out: Dict[int, Dict[str, float]] = {}

    for k in range(1, n + 1):
        d = base.get(k, None)
        if not d:
            out[k] = {"p_total": 0.0, "i_total": 0.0}
        else:
            out[k] = {"p_total": float(d.get("p_total", 0.0)), "i_total": float(d.get("i_total", 0.0))}
    return out

def compute_cc_aleatorios_totals(
    gabinetes: List[Dict[str, Any]],
    vmin: float,
) -> Dict[str, float]:
    """
    Totales de aleatorios seleccionados:
      - p_sel: suma p_eff de componentes "C.C. aleatorio" con cc_aleatorio_sel=True
      - i_sel: p_sel / vmin
    """
    if vmin <= 0:
        vmin = 1.0

    p_sel = 0.0

    for cab in gabinetes or []:
        for comp in (cab.get("components", []) or []):
            data = comp.get("data", {}) or {}
            tipo = str(data.get("tipo_consumo", "") or "").strip()
            if tipo != "C.C. aleatorio":
                continue

            if not bool(data.get("cc_aleatorio_sel", False)):
                continue

            p_eff = _effective_power_w(data)
            if p_eff <= 0:
                continue

            p_sel += p_eff

    return {"p_sel": float(p_sel), "i_sel": float(p_sel / vmin)}
