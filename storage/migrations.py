# -*- coding: utf-8 -*-
"""storage/migrations.py

Migraciones de estructura de proyectos (JSON) entre versiones.

Reglas:
- Funciones PURAS: reciben dict y devuelven dict (no IO).
- No dependen de PyQt.
- No hacen cálculos de ingeniería; sólo compatibilidad de datos.

Notas:
- Las migraciones deben ser idempotentes: volver a aplicarlas no debe romper nada.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

import uuid

from storage.project_schema import normalize_cabinet_entry


def _ensure_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _ensure_list(x: Any) -> list:
    return x if isinstance(x, list) else []


def migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """v1 -> v2

    - proyecto.frecuencia -> proyecto.frecuencia_hz
    - unifica instalaciones:{salas, gabinetes} si venía legacy.
    """
    d = deepcopy(data)
    proy = _ensure_dict(d.get("proyecto"))
    if "frecuencia_hz" not in proy and "frecuencia" in proy:
        proy["frecuencia_hz"] = proy.get("frecuencia")
    d["proyecto"] = proy

    # legacy -> instalaciones
    if not isinstance(d.get("instalaciones"), dict):
        ins = {"salas": [], "gabinetes": []}
        if isinstance(d.get("salas"), list):
            ins["salas"] = d.get("salas", [])
        if isinstance(d.get("gabinetes"), list):
            ins["gabinetes"] = d.get("gabinetes", [])
        d["instalaciones"] = ins

    ins = _ensure_dict(d.get("instalaciones"))
    ins.setdefault("salas", [])
    ins.setdefault("gabinetes", [])
    d["instalaciones"] = ins

    # meta
    meta = _ensure_dict(d.get("_meta"))
    meta["version"] = 2
    d["_meta"] = meta
    return d


def migrate_v2_to_v3(data: Dict[str, Any]) -> Dict[str, Any]:
    """v2 -> v3

    - Introduce configuración de Kt "no manual".
    - Mantiene compatibilidad con proyecto['ieee485_kt'] (manual).

    Nuevos campos recomendados en proyecto:
      - kt_mode: 'MANUAL' | 'IEEE_CURVE' | 'MANUFACTURER'
      - kt_final_vpc: Volts final por celda (si aplica)
      - kt_curve_source: 'IEEE' (placeholder)
      - kt_manufacturer_table: tabla opcional (placeholder)
    """
    d = deepcopy(data)
    proy = _ensure_dict(d.get("proyecto"))

    proy.setdefault("kt_mode", "MANUAL")
    proy.setdefault("kt_final_vpc", None)
    proy.setdefault("kt_curve_source", "IEEE")
    proy.setdefault("kt_manufacturer_table", None)

    # meta
    meta = _ensure_dict(d.get("_meta"))
    meta["version"] = 3
    d["_meta"] = meta
    d["proyecto"] = proy
    return d


def migrate_v3_to_v4(data: Dict[str, Any]) -> Dict[str, Any]:
    """v3 -> v4

    - Renombra 'salas' a 'ubicaciones' dentro de instalaciones.
    - Asegura IDs (UUID) para ubicaciones y gabinetes.
    - Gabinetes pasan a referenciar ubicacion por 'ubicacion_id' (se mantiene 'sala' legacy).
    """
    d = deepcopy(data)
    ins = _ensure_dict(d.get("instalaciones"))

    # --- salas/ubicaciones ---
    salas = ins.get("salas")
    ubic = ins.get("ubicaciones")
    if not isinstance(ubic, list):
        ubic = []
    if isinstance(salas, list) and not ubic:
        # mover legacy -> ubicaciones
        ubic = salas

    def _to_ubic_dict(x: Any) -> Dict[str, Any]:
        if isinstance(x, dict):
            tag = str(x.get("tag","") or x.get("TAG","") or "").strip()
            nombre = str(x.get("nombre","") or x.get("name","") or x.get("Nombre","") or "").strip()
            uid = str(x.get("id") or x.get("uuid") or "").strip()
            if not uid:
                uid = str(uuid.uuid4())
            return {"id": uid, "tag": tag, "nombre": nombre}
        if isinstance(x, (list, tuple)) and len(x) >= 2:
            tag = str(x[0] or "").strip()
            nombre = str(x[1] or "").strip()
            return {"id": str(uuid.uuid4()), "tag": tag, "nombre": nombre}
        # desconocido
        return {"id": str(uuid.uuid4()), "tag": "", "nombre": ""}

    ubic_norm = []
    seen_ids = set()
    for u in ubic:
        ud = _to_ubic_dict(u)
        # asegurar id único
        while ud["id"] in seen_ids:
            ud["id"] = str(uuid.uuid4())
        seen_ids.add(ud["id"])
        ubic_norm.append(ud)

    # index por tag para resolver gabinetes legacy
    by_tag = {}
    for ud in ubic_norm:
        t = (ud.get("tag") or "").strip()
        if t and t not in by_tag:
            by_tag[t] = ud

    # --- gabinetes ---
    gabs = _ensure_list(ins.get("gabinetes"))
    for g in gabs:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id") or g.get("uuid") or "").strip()
        if not gid:
            g["id"] = str(uuid.uuid4())
        else:
            g["id"] = gid

        # ubicacion_id
        if not str(g.get("ubicacion_id") or "").strip():
            sala_label = str(g.get("sala") or g.get("ubicacion") or "").strip()
            # label usual: "TAG - Nombre"
            tag = sala_label.split(" - ")[0].strip() if sala_label else ""
            if not tag and isinstance(g.get("sala"), dict):
                tag = str(g["sala"].get("tag","")).strip()
            if tag and tag in by_tag:
                g["ubicacion_id"] = by_tag[tag]["id"]

        # duplicar label en clave nueva sin romper legacy
        if "ubicacion" not in g and "sala" in g:
            g["ubicacion"] = g.get("sala")

    ins["ubicaciones"] = ubic_norm
    ins["gabinetes"] = gabs
    # mantener compatibilidad: borrar o dejar salas vacío
    ins.pop("salas", None)
    d["instalaciones"] = ins

    meta = _ensure_dict(d.get("_meta"))
    meta["version"] = 4
    d["_meta"] = meta
    return d

_MIGRATIONS = {
    (1, 2): migrate_v1_to_v2,
    (2, 3): migrate_v2_to_v3,
    (3, 4): migrate_v3_to_v4,
}


def migrate_project_dict(data: Dict[str, Any], *, from_version: int, to_version: int) -> Dict[str, Any]:
    """Migra un proyecto desde from_version hasta to_version."""
    d = deepcopy(data)
    v = int(from_version or 1)
    target = int(to_version)
    if v > target:
        # No intentamos "downgrade" automático
        return d

    while v < target:
        fn = _MIGRATIONS.get((v, v + 1))
        if fn is None:
            # Si falta una migración intermedia, paramos y forzamos version target
            meta = _ensure_dict(d.get("_meta"))
            meta["version"] = target
            d["_meta"] = meta
            return d
        d = fn(d)
        v += 1

    # asegura meta
    meta = _ensure_dict(d.get("_meta"))
    meta["version"] = target
    d["_meta"] = meta
    return d


def upgrade_project_dict(data: Any, *, to_version: int) -> Dict[str, Any]:
    """Normaliza y migra un dict cargado desde JSON a la versión actual.

    Incluye:
    - Migraciones entre versiones (migrate_project_dict)
    - Normalización estructural final (ids, pos/size, defaults mínimos)

    Esta función es PURA (no IO) y NO depende de PyQt.
    """
    if not isinstance(data, dict):
        data = {"_meta": {"version": 1}}

    d: Dict[str, Any] = deepcopy(data)

    meta = d.get("_meta", {})
    if not isinstance(meta, dict):
        meta = {}

    from_ver = int(meta.get("version", 1) or 1)
    d = migrate_project_dict(d, from_version=from_ver, to_version=int(to_version))

    # ---- Normalización: cc_escenarios legacy (list) -> dict ----
    try:
        proy = d.get("proyecto", {})
        if not isinstance(proy, dict):
            proy = {}
            d["proyecto"] = proy

        cc_esc = proy.get("cc_escenarios")

        # Formato legacy: lista de dicts [{"desc":"..."}, ...]
        if isinstance(cc_esc, list):
            cc_new = {}
            for i, it in enumerate(cc_esc, start=1):
                desc = ""
                if isinstance(it, dict):
                    desc = str(it.get("desc") or "").strip()
                elif it is not None:
                    desc = str(it).strip()
                if not desc:
                    desc = f"Escenario {i}"
                cc_new[str(i)] = desc

            proy["cc_escenarios"] = cc_new

        # Si es dict, lo dejamos tal cual.
    except Exception:
        import logging
        logging.getLogger(__name__).debug("Failed to normalize cc_escenarios (best-effort).", exc_info=True)


    # Normalización estructural final (id, pos/size, etc.)
    ins = d.get("instalaciones", {})
    if not isinstance(ins, dict):
        ins = {"ubicaciones": [], "gabinetes": []}
        d["instalaciones"] = ins

    gab_raw = ins.get("gabinetes", [])
    if not isinstance(gab_raw, list):
        gab_raw = []
    ins["gabinetes"] = [normalize_cabinet_entry(g) for g in gab_raw]

    # ---- Enlace estable: gabinetes <-> topología (ssaa_topology_layers) ----
    # Muchos proyectos antiguos guardaron feeder_key con índice (gi). Aquí inyectamos gabinete_id
    # en meta para que Cuadros de carga pueda resolver tableros sin depender del TAG.
    try:
        from core.keys import ProjectKeys as K
        topo_layers = (d.get("proyecto", {}) or {}).get(K.SSAA_TOPOLOGY_LAYERS, {}) or {}
        if isinstance(topo_layers, dict) and isinstance(ins.get("gabinetes", []), list):
            gabs = ins.get("gabinetes", [])
            for _ws, layer in topo_layers.items():
                if not isinstance(layer, dict):
                    continue
                for n in layer.get("nodes", []) or []:
                    if not isinstance(n, dict):
                        continue
                    nmeta = n.get("meta", {}) or {}
                    if not isinstance(nmeta, dict):
                        nmeta = {}
                    if nmeta.get("gabinete_id"):
                        continue
                    fk = str(nmeta.get("feeder_key") or n.get("feeder_key") or "")
                    # formato legado: "gabinete:<gi>:<ci>:<REQ>"
                    if fk.startswith("gabinete:"):
                        parts = fk.split(":")
                        if len(parts) >= 2:
                            try:
                                gi = int(parts[1])
                                if 0 <= gi < len(gabs):
                                    nmeta["gabinete_id"] = gabs[gi].get("id")
                                    n["meta"] = nmeta
                            except Exception:
                                import logging
                                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
    except Exception:
        import logging
        logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    # componentes derivado
    comp_section = d.get("componentes")
    if not isinstance(comp_section, dict):
        comp_section = {"gabinetes": []}
        d["componentes"] = comp_section
    if not comp_section.get("gabinetes"):
        from copy import deepcopy as _dc
        comp_section["gabinetes"] = [
            {"tag": g.get("tag", ""), "components": _dc(g.get("components", []))}
            for g in ins.get("gabinetes", [])
        ]

    meta = d.get("_meta", {})
    if not isinstance(meta, dict):
        meta = {}
    meta["version"] = int(to_version)
    d["_meta"] = meta
    return d