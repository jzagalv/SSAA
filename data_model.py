# -*- coding: utf-8 -*-
"""data_model.py

Persistencia + estado de edición (dirty flag) + versionado/migraciones.

Regla: este módulo NO depende de PyQt.
La UI es la responsable de mostrar QMessageBox o notificaciones.
"""

from __future__ import annotations


from typing import Any, Callable, Dict, List, Optional
from core.sections import Section
import json
import logging
import os
import uuid
from copy import deepcopy
from infra.text_encoding import fix_mojibake_deep

from storage.schema import PROJECT_VERSION
from storage.migrations import migrate_project_dict, upgrade_project_dict
from storage.project_paths import PROJECT_EXT, norm_project_path as _norm_project_path
from storage.project_serialization import to_project_dict as _to_project_dict
from storage.project_serialization import apply_project_dict as _apply_project_dict
from storage.project_schema import (
    normalize_sala_entry,
    normalize_component_data,
    normalize_cabinet_entry,
    norm_pos,
    norm_size,
)
from domain.models.project import Project


# Backward-compat: nombre histórico. Mantener para imports antiguos.
def _norm_json_path(folder: str, filename: str) -> str:
    return _norm_project_path(folder, filename, ext=PROJECT_EXT)


class DataModel:
    """
    Única fuente de datos. Secciones:
      - proyecto       (pantalla Proyecto)
      - instalaciones  (salas/gabinetes)
      - componentes    (componentes por gabinete)
    Maneja ubicación del archivo y flag 'dirty' para confirmar guardados.
    """
    def __init__(self):
        # Event bus (NO PyQt dependency). UI/controller can subscribe.
        # Events: 'section_changed', 'project_loaded', 'project_saved', 'dirty_changed'.
        self._listeners = {}
        self._dirty = False
        self.revision = 0
        self._ui_refreshing = False  # evita marcar dirty durante refrescos UI
        self._is_loading = False     # evita side-effects durante load
        self.clear()

    # ----------------- events (observer pattern) -----------------
    def on(self, event: str, callback):
        """Subscribe to a DataModel event.

        callback signature depends on event:
          - section_changed(section: str)
          - project_loaded(file_path: str)
          - project_saved(file_path: str)
          - dirty_changed(is_dirty: bool)
        """
        if not event or not callable(callback):
            return
        self._listeners.setdefault(event, []).append(callback)

    def off(self, event: str, callback):
        if not event or event not in self._listeners:
            return
        try:
            self._listeners[event] = [cb for cb in self._listeners[event] if cb is not callback]
        except Exception:
            pass

    def _emit(self, event: str, *args, **kwargs):
        for cb in list(self._listeners.get(event, []) or []):
            try:
                cb(*args, **kwargs)
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def notify_section_changed(self, section, *, mark_dirty: bool = True):
        """Notify that a logical section changed.

        Contract:
          - Callers must emit a Section enum (preferred).
          - In debug, passing a raw string raises (to prevent regressions).
        """
        # Enforce enum-based section keys (contract).
        if isinstance(section, str) and not isinstance(section, Section):
            if __debug__:
                raise TypeError("notify_section_changed expects a Section enum, not raw str")
            section = Section(section)
        elif not isinstance(section, Section):
            section = Section(str(section))

        key = section  # keep Section enum internally

        if mark_dirty:
            self.mark_dirty(True)
        self._emit('section_changed', key)

    def notify_section_viewed(self, section):
        """Notify that a section/view was *activated* (e.g. tab change).

        Design contract:
          - Viewing a screen must not trigger heavy recalculations.
          - The orchestrator may refresh UI from the current model snapshot.

        We keep the same enum contract as notify_section_changed.
        """
        # Enforce enum-based section keys (contract).
        if isinstance(section, str) and not isinstance(section, Section):
            if __debug__:
                raise TypeError("notify_section_viewed expects a Section enum, not raw str")
            section = Section(section)
        elif not isinstance(section, Section):
            section = Section(str(section))

        self._emit('section_viewed', section)

    def notify_project_loaded(self, file_path: str):
        self._emit('project_loaded', file_path or '')

    def notify_project_saved(self, file_path: str):
        self._emit('project_saved', file_path or '')

    def notify_dirty_changed(self, is_dirty: bool):
        self._emit('dirty_changed', bool(is_dirty))

    def invalidate_feeding_validation(self):
        """Notify subscribers that feeding validations should be recomputed."""
        self._emit('feeding_validation_invalidated')

    # ----------------- estado general -----------------
    def clear(self):
        # archivo
        self.project_folder = ""
        self.project_filename = ""   # sin extensión (.ssaa)
        self.file_path = ""
        self.file_name = ""

        # SSOT project model (optional)
        self.project_model = None

        # ----------------- librerías externas -----------------
        # Las librerías (consumos/materiales) son GLOBALes y sirven para
        # proponer datos/estandarizar. Importante: al abrir un proyecto, NO se
        # debe modificar ninguna selección/dato automáticamente por cambios en
        # la librería; las actualizaciones deben ser explícitas por el usuario.
        self.library_paths = {
            "consumos": "",      # ruta a *.lib
            "materiales": "",    # ruta a *.lib
        }
        self.library_data = {
            "consumos": None,      # dict cargado
            "materiales": None,    # dict cargado
        }

        # cambios pendientes
        self._dirty = False

        # secciones
        self.proyecto = {
            "cliente": "", "project_number": "", "tag_room": "",
            "doc_isep": "", "doc_cliente": "",
            "altura": None,

            # Tensiones AC (si las usas)
            "tension_monofasica": None,
            "tension_trifasica": None,
            "max_voltaje": None,
            "min_voltaje": None,
            "frecuencia_hz": None,

            # Tensiones DC
            "tension_nominal": None,
            "max_voltaje_cc": None,
            "min_voltaje_cc": None,

            # Banco/cargador
            "num_cargadores": None,
            "num_bancos": None,
            "porcentaje_utilizacion": None,
            "tension_flotacion_celda": None,
            "num_celdas_usuario": None,

            # CC
            "cc_usar_pct_global": True,
            "cc_num_escenarios": 1,
            "cc_escenarios": {},
            "cc_scenarios_summary": [],
            "perfil_cargas": [],
        }

        self.instalaciones = {"ubicaciones": [], "gabinetes": []}
        self.componentes = {"gabinetes": []}

        # root dict view (compat)
        self.project = {"proyecto": self.proyecto, "instalaciones": self.instalaciones, "componentes": self.componentes}

        # alias legacy (por compatibilidad con pantallas existentes)
        self.components = []
        self.ubicaciones = self.instalaciones["ubicaciones"]
        self.salas = self.ubicaciones  # alias legacy
        self.gabinetes = self.instalaciones["gabinetes"]

    # ----------------- archivo -----------------
    def set_project_location(self, folder: str, filename: str):
        """Define carpeta y nombre (sin extensión)."""
        self.project_folder = (folder or "").strip()
        self.project_filename = os.path.splitext((filename or "").strip())[0]
        self.file_path = _norm_project_path(self.project_folder, self.project_filename)
        self.file_name = os.path.basename(self.file_path) if self.file_path else ""

    def has_project_file(self) -> bool:
        """¿Ya hay carpeta + nombre definidos? (sin doble .json)"""
        folder = getattr(self, "project_folder", "") or ""
        filename = getattr(self, "project_filename", "") or ""
        base, ext = os.path.splitext(filename)
        if ext.lower() in ('.json', '.ssaa'):
            filename = base
        return bool(folder.strip() and filename.strip())

    @property
    def dirty(self) -> bool:
        return bool(getattr(self, "_dirty", False))

    @dirty.setter
    def dirty(self, v: bool):
        self._dirty = bool(v)

    def mark_dirty(self, v: bool = True):
        # Durante refrescos automáticos de UI (reload/recalc),
        # evitamos marcar el proyecto como modificado si el usuario no tocó nada.
        if v and getattr(self, '_ui_refreshing', False):
            return
        prev = bool(getattr(self, "dirty", False))
        new = bool(v)
        self.dirty = new
        if prev != new:
            if new:
                self.bump_revision()
            try:
                self._emit("dirty_changed", new)
            except Exception:
                import logging
                logging.getLogger(__name__).debug("Ignored exception (best-effort).", exc_info=True)

    def bump_revision(self) -> None:
        if bool(getattr(self, "_ui_refreshing", False)):
            return
        try:
            self.revision = int(getattr(self, "revision", 0)) + 1
        except Exception:
            self.revision = 1

    def set_cc_results(self, results: dict, *, notify: bool = False) -> None:
        """Set derived CC results without emitting InputChanged."""
        if not isinstance(getattr(self, "proyecto", None), dict):
            return
        self.proyecto["cc_results"] = results if isinstance(results, dict) else {}
        if notify and hasattr(self, "notify_section_changed"):
            self.notify_section_changed(Section.CC, mark_dirty=False)

    def get_cc_inputs_snapshot(self) -> dict:
        """Return a safe snapshot of CC inputs (no cc_results, no Qt objects)."""
        proj = getattr(self, "proyecto", {}) or {}
        snap = deepcopy(proj) if isinstance(proj, dict) else {}
        if isinstance(snap, dict):
            snap.pop("cc_results", None)
        return snap

    def set_ui_refreshing(self, v: bool):
        self._ui_refreshing = bool(v)
    @staticmethod
    def _load_json_file(path: str) -> dict:
        if not path:
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return fix_mojibake_deep(data)

    def set_library_path(self, kind: str, path: str):
        kind = (kind or "").strip().lower()
        if kind not in ("consumos", "materiales"):
            raise ValueError("Tipo de librería inválido")
        self.library_paths[kind] = path or ""
        if getattr(self, 'project_model', None) is not None:
            self.project_model.library_links[kind] = path or ""


    def resolve_library_path(self, path: str) -> str:
        """Resuelve rutas de librerías.

        - Si `path` es absoluta, se retorna tal cual.
        - Si es relativa, se intenta resolver contra la carpeta del proyecto (`project_folder`).
        - Si no existe, se retorna el path original (para que el llamador decida).
        """
        if not path:
            return ""
        try:
            from pathlib import Path
            p = Path(path)
            if p.is_absolute():
                return str(p)
            base = getattr(self, "project_folder", "") or ""
            if base:
                candidate = Path(base) / p
                if candidate.exists():
                    return str(candidate)
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
        return path


    def load_library(self, kind: str, path: str) -> dict:
        """Carga una librería .lib (JSON plano) y valida su header.

        kind: 'consumos' o 'materiales'
        Retorna el dict cargado si es válido.
        Levanta ValueError si no es compatible.
        """
        kind = (kind or "").strip().lower()
        if kind not in ("consumos", "materiales"):
            raise ValueError("Tipo de librería inválido")

        path = self.resolve_library_path(path)

        data = self._load_json_file(path)

        # Compatibilidad: antiguas bases en JSON (p.ej. component_database.json)
        # que traían la clave "components".
        if kind == "consumos" and isinstance(data, dict) and "items" not in data and "components" in data:
            data = self._convert_component_database_to_consumos_lib(data)

        # Asegurar identidad estable de cada ítem de librería.
        # Esto permite enlazar consumos del proyecto a la librería por UUID.
        if kind == "consumos":
            self._ensure_consumos_lib_uids(data)
        elif kind == "materiales":
            self._ensure_materiales_lib_ids(data)

        file_type = str(data.get("file_type", "")).strip()

        expected = {
            "consumos": "SSAA_LIB_CONSUMOS",
            "materiales": "SSAA_LIB_MATERIALES",
        }[kind]
        if file_type != expected:
            raise ValueError(
                f"El archivo seleccionado no corresponde a '{expected}'.\n"
                f"file_type encontrado: '{file_type or '(vacío)'}'"
            )

        schema_version = data.get("schema_version", 1)
        # Reservado para migraciones futuras de librería
        if not isinstance(schema_version, int) or schema_version < 1:
            raise ValueError("schema_version inválido en la librería")

        self.library_paths[kind] = path
        if getattr(self, 'project_model', None) is not None:
            self.project_model.library_links[kind] = path or ""
        self.library_data[kind] = data
        return data

    @staticmethod
    def _ensure_materiales_lib_ids(lib: dict) -> None:
        """Normaliza estructura mínima e IDs de SSAA_LIB_MATERIALES.

        Estructura esperada (schema_version=1):

        {
          "file_type": "SSAA_LIB_MATERIALES",
          "schema_version": 1,
          "name": "Materiales",
          "items": {
             "batteries": [ {"id": "...", ...} ],
             "battery_banks": [],
             "mcb": [], "mccb": [], "rccb": [], "rccb_mcb": []
          }
        }

        Esta función NO guarda el archivo; solo normaliza el dict cargado.
        """
        if not isinstance(lib, dict):
            return

        items = lib.get("items")
        if not isinstance(items, dict):
            # compat: formatos antiguos (listas directas)
            items = {}
            lib["items"] = items

        # Asegurar listas por categoría
        for k in ("batteries", "battery_banks", "mcb", "mccb", "rccb", "rccb_mcb"):
            v = items.get(k)
            if not isinstance(v, list):
                items[k] = []

        # IDs estables en baterías
        seen = set()
        for it in items.get("batteries", []) or []:
            if not isinstance(it, dict):
                continue
            _id = str(it.get("id", "") or "").strip()
            if not _id or _id in seen:
                _id = f"bat_{uuid.uuid4().hex[:10]}"
                it["id"] = _id
            seen.add(_id)


    @staticmethod
    def _ensure_consumos_lib_uids(lib: dict) -> None:
        """Garantiza que cada item de SSAA_LIB_CONSUMOS tenga un lib_uid (UUID) y un code.

        - lib_uid: identificador único e inmutable.
        - code: identificador humano (puede estar vacío).

        Nota: Esta función NO guarda el archivo; solo normaliza el dict cargado.
        """
        if not isinstance(lib, dict):
            return
        items = lib.get("items")
        if not isinstance(items, list):
            return

        seen = set()
        for it in items:
            if not isinstance(it, dict):
                continue

            uid = str(it.get("lib_uid", "") or "").strip()
            try:
                # Normalizamos cualquier uuid válido
                uid = str(uuid.UUID(uid)) if uid else ""
            except Exception:
                uid = ""

            if not uid or uid in seen:
                uid = str(uuid.uuid4())
                it["lib_uid"] = uid
            seen.add(uid)

            # code humano (opcional)
            if "code" not in it or it.get("code") is None:
                it["code"] = ""

    @staticmethod
    def _convert_component_database_to_consumos_lib(old: dict) -> dict:
        """Convierte el formato antiguo resources/component_database.json al formato .lib de consumos."""
        items = []
        for c in old.get("components", []) or []:
            if not isinstance(c, dict):
                continue
            items.append(
                {
                    "lib_uid": str(uuid.uuid4()),
                    "code": "",
                    "name": c.get("name", ""),
                    "marca": c.get("marca", ""),
                    "modelo": c.get("modelo", ""),
                    "potencia_w": c.get("potencia_w", 0.0),
                    "potencia_va": c.get("potencia_va", None),
                    "usar_va": bool(c.get("usar_va", False)),
                    "alimentador": c.get("alimentador", "Individual"),
                    "tipo_consumo": c.get("tipo_consumo", ""),
                    "fase": c.get("fase", ""),
                }
            )

        meta_in = old.get("meta", {}) if isinstance(old.get("meta", {}), dict) else {}
        return {
            "file_type": "SSAA_LIB_CONSUMOS",
            "schema_version": 1,
            "name": str(meta_in.get("name", "Consumos")).strip() or "Consumos",
            "items": items,
        }

    def update_project_from_consumos_library(self) -> dict:
        """Actualiza consumos del proyecto usando la librería de consumos.

        Esto SOLO debe ejecutarse por acción explícita del usuario.

        Criterio:
        - Se actualizan campos técnicos (marca/modelo/potencia/tipo/fase/usar_va)
          **solo** para consumos cuyo origen NO sea "Por Usuario".
        - No se toca TAG, alimentador, posición, tamaño, ni otras selecciones.
        - Se hace match por nombre del consumo: comp['base'] (o comp['name'] si falta).

        Retorna un resumen con contadores para mostrar en UI.
        """
        lib = (self.library_data or {}).get("consumos")
        if not isinstance(lib, dict) or lib.get("file_type") != "SSAA_LIB_CONSUMOS":
            raise ValueError("No hay una librería de consumos válida cargada.")

        items = lib.get("items", [])
        if not isinstance(items, list):
            raise ValueError("La librería de consumos no contiene 'items' válido.")

        # Índices de búsqueda (preferir lib_uid si existe)
        by_uid = {}
        by_name = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            uid = str(it.get("lib_uid", "") or "").strip()
            name = str(it.get("name", "") or "").strip()
            if uid:
                by_uid[uid] = it
            if name:
                by_name[name] = it

        updated = 0
        skipped_user = 0
        not_found = 0
        touched_cabinets = 0

        gabinetes = getattr(self, "gabinetes", []) or []
        for cab in gabinetes:
            if not isinstance(cab, dict):
                continue
            comps = cab.get("components", [])
            if not isinstance(comps, list) or not comps:
                continue

            cab_touched = False
            for comp in comps:
                if not isinstance(comp, dict):
                    continue
                base = str(comp.get("base") or comp.get("name") or "").strip()
                if not base:
                    continue

                data = comp.get("data") or {}
                data = self._normalize_component_data(data)

                if str(data.get("origen", "")) == "Por Usuario":
                    skipped_user += 1
                    continue

                # Preferir vínculo por lib_uid (si el consumo fue insertado desde librería)
                src = None
                src_uid = None
                try:
                    src_uid = str((comp.get("source") or {}).get("lib_uid", "") or "").strip()
                except Exception:
                    src_uid = None
                if src_uid:
                    src = by_uid.get(src_uid)
                if not src:
                    src = by_name.get(base)
                if not src:
                    not_found += 1
                    continue

                src_n = self._normalize_component_data(src)

                # Campos que SI actualizamos
                for k in (
                    "marca",
                    "modelo",
                    "potencia_w",
                    "potencia_va",
                    "usar_va",
                    "tipo_consumo",
                    "fase",
                ):
                    if k in src_n and src_n.get(k) is not None:
                        data[k] = src_n.get(k)

                comp["data"] = data

                # Trazabilidad: registrar el vínculo a librería (si aplica)
                if src_uid:
                    source = comp.get("source") if isinstance(comp.get("source"), dict) else {}
                    source["lib_uid"] = src_uid
                    source["code"] = str(src.get("code", source.get("code", "")) or "")
                    source["lib_path"] = str(getattr(self, "library_paths", {}).get("consumos", "") or "")
                    source["last_sync_from_lib"] = True
                    comp["source"] = source
                updated += 1
                cab_touched = True

            if cab_touched:
                touched_cabinets += 1

        if updated:
            self.mark_dirty(True)

            # Trazabilidad: dejar registrado qué librería de consumos se aplicó.
            if isinstance(self.project, dict):
                libs = self.project.setdefault("libraries", {})
                if isinstance(libs, dict):
                    cons = libs.setdefault("consumos", {})
                    if isinstance(cons, dict):
                        cons["last_applied_path"] = self.library_paths.get("consumos")

            # Registrar trazabilidad de la última librería aplicada (útil para proyectos antiguos).
            try:
                libs = self.project.setdefault("libraries", {}) if isinstance(self.project, dict) else None
                if isinstance(libs, dict):
                    cons = libs.setdefault("consumos", {})
                    if isinstance(cons, dict):
                        cons["last_applied_path"] = str(self.library_paths.get("consumos", ""))
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        return {
            "updated": updated,
            "skipped_user": skipped_user,
            "not_found": not_found,
            "touched_cabinets": touched_cabinets,
        }

    def build_consumos_update_plan(self) -> list:
        """Genera una lista (tipo diff) de los consumos que CAMBIARÍAN al
        actualizar el proyecto con la librería de consumos actualmente cargada.

        Retorna una lista de entradas con:
          - cabinet_tag, cabinet_desc
          - component_name (base)
          - indices (cab_idx, comp_idx)
          - changes: {campo: {"old": x, "new": y}}

        Nota: Solo considera consumos cuyo origen != "Por Usuario".
        """
        lib = (self.library_data or {}).get("consumos")
        if not isinstance(lib, dict) or lib.get("file_type") != "SSAA_LIB_CONSUMOS":
            raise ValueError("No hay una librería de consumos válida cargada.")

        items = lib.get("items", [])
        if not isinstance(items, list):
            raise ValueError("La librería de consumos no contiene 'items' válido.")

        by_uid = {}
        by_name = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            uid = str(it.get("lib_uid", "") or "").strip()
            if uid:
                by_uid[uid] = it
            n = str(it.get("name", "")).strip()
            if n:
                by_name[n] = it

        plan = []
        gabinetes = getattr(self, "gabinetes", []) or []
        fields = (
            "marca",
            "modelo",
            "potencia_w",
            "potencia_va",
            "usar_va",
            "tipo_consumo",
            "fase",
        )

        for cab_idx, cab in enumerate(gabinetes):
            if not isinstance(cab, dict):
                continue
            comps = cab.get("components", [])
            if not isinstance(comps, list) or not comps:
                continue

            for comp_idx, comp in enumerate(comps):
                if not isinstance(comp, dict):
                    continue
                base = str(comp.get("base") or comp.get("name") or "").strip()
                if not base:
                    continue

                data = self._normalize_component_data(comp.get("data") or {})
                if str(data.get("origen", "")) == "Por Usuario":
                    continue

                # Match preferente por lib_uid (si existe), fallback por nombre.
                src = None
                src_uid = None
                src_info = comp.get("source") if isinstance(comp.get("source"), dict) else {}
                src_uid = str(src_info.get("lib_uid", "") or "").strip() if isinstance(src_info, dict) else ""
                if src_uid:
                    src = by_uid.get(src_uid)
                if not src:
                    src = by_name.get(base)
                if not src:
                    continue
                src_n = self._normalize_component_data(src)

                changes = {}
                for k in fields:
                    if k in src_n and src_n.get(k) is not None:
                        old = data.get(k)
                        new = src_n.get(k)
                        if old != new:
                            changes[k] = {"old": old, "new": new}

                if changes:
                    sala = str(cab.get("sala", "")).strip()
                    cab_tag = str(cab.get("tag", "")).strip()
                    # En este proyecto el nombre del gabinete viene como "nombre" (no "descripcion")
                    cab_nombre = str(cab.get("nombre", cab.get("descripcion", ""))).strip()
                    gabinete_ui = " - ".join([x for x in (cab_tag, cab_nombre) if x])

                    plan.append(
                        {
                            "cab_idx": cab_idx,
                            "comp_idx": comp_idx,
                            # claves internas
                            "cabinet_tag": cab_tag,
                            "cabinet_desc": cab_nombre,
                            "component_name": base,
                            # claves para UI (tabla diff)
                            "instalacion": sala,
                            "gabinete": gabinete_ui,
                            "consumo": base,
                            "changes": changes,
                        }
                    )

        return plan

    def apply_consumos_update_plan(self, plan: list, selected_ids: set | None = None) -> dict:
        """Aplica un plan de actualización (generado por build_consumos_update_plan).

        Si selected_ids es None -> aplica todo.
        Si es set de índices -> aplica solo esas filas del plan.
        """
        if not isinstance(plan, list):
            raise ValueError("Plan de actualización inválido.")

        gabinetes = getattr(self, "gabinetes", []) or []
        updated = 0
        touched_cabinets = set()

        for i, entry in enumerate(plan):
            if selected_ids is not None and i not in selected_ids:
                continue
            try:
                cab_idx = int(entry.get("cab_idx"))
                comp_idx = int(entry.get("comp_idx"))
            except Exception:
                continue
            if cab_idx < 0 or cab_idx >= len(gabinetes):
                continue
            cab = gabinetes[cab_idx]
            comps = cab.get("components", [])
            if not isinstance(comps, list) or comp_idx < 0 or comp_idx >= len(comps):
                continue
            comp = comps[comp_idx]
            data = self._normalize_component_data(comp.get("data") or {})
            changes = entry.get("changes") or {}
            if not isinstance(changes, dict) or not changes:
                continue
            for k, ch in changes.items():
                if isinstance(ch, dict) and "new" in ch:
                    data[k] = ch["new"]
            comp["data"] = data
            updated += 1
            touched_cabinets.add(cab_idx)

        if updated:
            self.mark_dirty(True)

            # Trazabilidad: registrar la última librería de consumos aplicada.
            if isinstance(self.project, dict):
                libs = self.project.setdefault("libraries", {})
                cons = libs.setdefault("consumos", {}) if isinstance(libs, dict) else None
                if isinstance(cons, dict):
                    current_path = self.library_paths.get("consumos")
                    if current_path:
                        cons["last_applied_path"] = current_path

        return {
            "updated": updated,
            "touched_cabinets": len(touched_cabinets),
        }

    # ----------------- compat helpers -----------------
    def _sync_aliases_out(self):
        if getattr(self, 'project_model', None) is not None:
            self.instalaciones['ubicaciones'] = self.project_model.installations.ubicaciones
            self.instalaciones['gabinetes'] = self.project_model.installations.cabinets_view
            self.ubicaciones = self.instalaciones['ubicaciones']
            self.salas = self.ubicaciones
            self.gabinetes = self.instalaciones['gabinetes']
            self._enforce_alias_identity()
            return
        self.salas = self.instalaciones['ubicaciones']
        self.gabinetes = self.instalaciones['gabinetes']
        self._enforce_alias_identity()

    def _sync_aliases_in(self):
        if getattr(self, 'project_model', None) is not None:
            self.instalaciones['ubicaciones'] = self.project_model.installations.ubicaciones
            self.instalaciones['gabinetes'] = self.project_model.installations.cabinets_view
            self.ubicaciones = self.instalaciones['ubicaciones']
            self.salas = self.ubicaciones
            self.gabinetes = self.instalaciones['gabinetes']
            return
        if self.salas is not self.instalaciones['ubicaciones']:
            self.salas = self.instalaciones['ubicaciones']
        if self.gabinetes is not self.instalaciones['gabinetes']:
            self.gabinetes = self.instalaciones['gabinetes']

    def ensure_aliases_consistent(self):
        """Best-effort sync between legacy aliases and instalaciones."""
        def _count_components(gabs):
            total = 0
            for g in gabs or []:
                if not isinstance(g, dict):
                    continue
                comps = g.get("components", []) or []
                total += len(comps)
            return total

        try:
            self._sync_aliases_in()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        try:
            self._sync_aliases_out()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        instalaciones = getattr(self, "instalaciones", None)
        if not isinstance(instalaciones, dict):
            return

        gab_inst = instalaciones.get("gabinetes", None)
        gab_alias = getattr(self, "gabinetes", None)

        if isinstance(gab_inst, list) and isinstance(gab_alias, list) and gab_inst and gab_alias:
            comp_inst = _count_components(gab_inst)
            comp_alias = _count_components(gab_alias)
            if comp_alias > comp_inst:
                canonical = gab_alias
            elif comp_inst > comp_alias:
                canonical = gab_inst
            else:
                canonical = gab_alias
            instalaciones["gabinetes"] = canonical
            self.gabinetes = canonical
            return

        if isinstance(gab_alias, list) and gab_alias and (
            not isinstance(gab_inst, list) or len(gab_inst) == 0
        ):
            instalaciones["gabinetes"] = gab_alias
            self.gabinetes = gab_alias
            return

        if isinstance(gab_inst, list) and gab_inst and (
            not isinstance(gab_alias, list) or len(gab_alias) == 0
        ):
            if isinstance(gab_alias, list):
                self.gabinetes = gab_inst
            else:
                self.gabinetes = gab_inst

    def _check_cabinet_views(self):
        if getattr(self, 'project_model', None) is None:
            return
        try:
            if id(self.instalaciones.get('gabinetes')) != id(self.project_model.installations.cabinets_view):
                import logging
                logging.getLogger(__name__).warning("Cabinet views desaligned (SSOT breach).")
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def _enforce_alias_identity(self) -> None:
        """Ensure SSOT identity for gabinetes/ubicaciones aliases (best-effort)."""
        try:
            ins = self.instalaciones if isinstance(self.instalaciones, dict) else {}
            gabs = ins.get("gabinetes")
            locs = ins.get("ubicaciones")
            if gabs is not None and getattr(self, "gabinetes", None) is not gabs:
                logging.getLogger(__name__).warning("SSOT guardrail: realigning gabinetes alias.")
                self.gabinetes = gabs
            if locs is not None:
                if getattr(self, "ubicaciones", None) is not locs:
                    logging.getLogger(__name__).warning("SSOT guardrail: realigning ubicaciones alias.")
                    self.ubicaciones = locs
                if getattr(self, "salas", None) is not locs:
                    logging.getLogger(__name__).warning("SSOT guardrail: realigning salas alias.")
                    self.salas = locs
            if __debug__:
                if gabs is not None:
                    assert self.gabinetes is gabs
                if locs is not None:
                    assert self.ubicaciones is locs
                    assert self.salas is locs
        except Exception:
            logging.getLogger(__name__).debug("SSOT guardrail failed (best-effort).", exc_info=True)

    def set_project(self, project: Project) -> None:
        self.project_model = project
        if self.project_model is None:
            return
        self.project_model.sync_views()
        self.proyecto = self.project_model.proyecto_dict
        self.instalaciones['ubicaciones'] = self.project_model.installations.ubicaciones
        self.instalaciones['gabinetes'] = self.project_model.installations.cabinets_view
        self.ubicaciones = self.instalaciones['ubicaciones']
        self.salas = self.ubicaciones
        self.gabinetes = self.instalaciones['gabinetes']
        # Derived components view (compat)
        try:
            self.componentes['gabinetes'] = [
                {"tag": g.get("tag", ""), "components": g.get("components", [])}
                for g in self.instalaciones.get('gabinetes', [])
            ]
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
        # root dict view (compat)
        self.project = {"proyecto": self.proyecto, "instalaciones": self.instalaciones, "componentes": self.componentes}
        self._check_cabinet_views()

    def get_cabinets(self):
        if getattr(self, 'project_model', None) is not None:
            return self.project_model.installations.cabinets
        return self.instalaciones.get('gabinetes', [])

    # ----------------- helpers de normalización -----------------
    @staticmethod
    def _normalize_sala_entry(sala):
        """Wrapper: delega a storage.project_schema.normalize_sala_entry."""
        return normalize_sala_entry(sala)

    @staticmethod
    def _normalize_component_data(data: dict) -> dict:
        """Wrapper: delega a storage.project_schema.normalize_component_data."""
        return normalize_component_data(data)

    # ✅ helpers reales de geometría (a nivel de clase)
    @staticmethod
    def _norm_pos(v):
        return norm_pos(v)

    @staticmethod
    def _norm_size(v, default_w=260.0, default_h=120.0):
        return norm_size(v, default_w=default_w, default_h=default_h)

    @staticmethod
    def _normalize_cabinet_entry(gab: dict) -> dict:
        """Wrapper: delega a storage.project_schema.normalize_cabinet_entry."""
        return normalize_cabinet_entry(gab)

    @staticmethod
    def upgrade_dict(data: dict) -> dict:
        """Wrapper: migra + normaliza usando storage.migrations.upgrade_project_dict."""
        return upgrade_project_dict(data, to_version=PROJECT_VERSION)

    # ----------------- serialización -----------------
    def to_dict(self) -> dict:
        # Wrapper: serialización real vive en storage.project_serialization
        return _to_project_dict(self)

    def from_dict(self, data: dict, file_path: str = ""):
        # Wrapper: deserialización real vive en storage.project_serialization
        _apply_project_dict(self, data, file_path=file_path)
        try:
            prev = bool(getattr(self, "_ui_refreshing", False))
            self._ui_refreshing = False
            self.bump_revision()
            self._ui_refreshing = prev
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    # ----------------- I/O -----------------
    # ----------------- I/O -----------------
    def save_to_file(self, file_path: str = "") -> bool:
        """Save project JSON to disk.

        Wrapper kept for backward compatibility; actual I/O lives in storage.project_io.
        """
        from storage.project_io import save_project
        return save_project(self, file_path=file_path)

    def load_from_file(self, file_path: str) -> bool:
        """Load project JSON from disk.

        Wrapper kept for backward compatibility; actual I/O lives in storage.project_io.
        """
        from infra.perf import span as perf_span
        from storage.project_io import load_project
        with perf_span(f"load_project {file_path}", threshold_ms=50.0):
            ok = load_project(self, file_path=file_path)
        return ok
