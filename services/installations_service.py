# -*- coding: utf-8 -*-
"""Service layer for instalaciones (ubicaciones + gabinetes).

This module is UI-agnostic and must not import PyQt.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


class InstallationsService:
    """CRUD and validations for instalaciones data."""

    def __init__(self, dm_or_installations: Any):
        self._source = dm_or_installations

    # -------- internal helpers --------
    def _store(self) -> Dict[str, Any]:
        if isinstance(self._source, dict):
            store = self._source
        else:
            store = getattr(self._source, "instalaciones", None)
        if not isinstance(store, dict):
            raise ValueError("DataModel invalido: instalaciones no disponible")
        if not isinstance(store.get("ubicaciones"), list):
            store["ubicaciones"] = list(store.get("ubicaciones") or [])
        if not isinstance(store.get("gabinetes"), list):
            store["gabinetes"] = list(store.get("gabinetes") or [])
        return store

    def _ubicaciones(self) -> List[Any]:
        return self._store()["ubicaciones"]

    def _gabinetes(self) -> List[Any]:
        return self._store()["gabinetes"]

    @staticmethod
    def _clean_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _sala_parts(sala: Any) -> tuple[str, str]:
        if isinstance(sala, (tuple, list)) and len(sala) >= 2:
            return str(sala[0] or ""), str(sala[1] or "")
        if isinstance(sala, dict):
            return str(sala.get("tag", "") or ""), str(sala.get("nombre", "") or "")
        return "", ""

    @staticmethod
    def _sala_label(tag: str, nombre: str) -> str:
        return f"{tag} - {nombre}" if nombre else tag

    def _find_ubicacion_by_tag(self, tag: str) -> Optional[Dict[str, Any]]:
        tag = self._clean_text(tag)
        for u in self._ubicaciones():
            if isinstance(u, dict) and self._clean_text(u.get("tag")) == tag:
                return u
        return None

    def _find_ubicacion_by_label_or_tag(self, label_or_tag: str) -> Optional[Dict[str, Any]]:
        needle = self._clean_text(label_or_tag)
        if not needle:
            return None
        for u in self._ubicaciones():
            if not isinstance(u, dict):
                continue
            tag, nombre = self._sala_parts(u)
            label = self._sala_label(tag, nombre)
            if needle == tag or needle == label:
                return u
        return None

    def _validate_ubicacion_data(self, tag: str, nombre: str, *, skip_index: Optional[int] = None) -> tuple[str, str]:
        tag = self._clean_text(tag)
        nombre = self._clean_text(nombre)
        if not tag or not nombre:
            raise ValueError("Complete ambos campos")
        for idx, sala in enumerate(self._ubicaciones()):
            existing_tag, _ = self._sala_parts(sala)
            if idx != skip_index and existing_tag == tag:
                raise ValueError("TAG ya existe")
        return tag, nombre

    def _validate_gabinete_data(
        self,
        tag: str,
        nombre: str,
        ubic_tag: str,
        *,
        skip_index: Optional[int] = None,
    ) -> tuple[str, str, Dict[str, Any]]:
        tag = self._clean_text(tag)
        nombre = self._clean_text(nombre)
        ubic_tag = self._clean_text(ubic_tag)
        if not tag or not nombre or not ubic_tag:
            raise ValueError("Complete todos los campos")
        for idx, gabinete in enumerate(self._gabinetes()):
            if not isinstance(gabinete, dict):
                continue
            if idx != skip_index and self._clean_text(gabinete.get("tag")) == tag:
                raise ValueError("TAG ya existe")
        ubic = self._find_ubicacion_by_tag(ubic_tag)
        if ubic is None:
            raise ValueError("Seleccione una ubicacion")
        return tag, nombre, ubic

    def _require_index(self, index: int, items: List[Any], empty_message: str) -> int:
        if not isinstance(index, int) or index < 0 or index >= len(items):
            raise ValueError(empty_message)
        return index

    # -------- ubicaciones --------
    def add_ubicacion(self, tag, nombre) -> None:
        tag, nombre = self._validate_ubicacion_data(tag, nombre)
        self._ubicaciones().append({"id": str(uuid.uuid4()), "tag": tag, "nombre": nombre})

    def edit_ubicacion(self, index, tag, nombre) -> None:
        idx = self._require_index(index, self._ubicaciones(), "Seleccione una ubicacion")
        tag, nombre = self._validate_ubicacion_data(tag, nombre, skip_index=idx)
        current = self._ubicaciones()[idx]
        if isinstance(current, dict):
            current.setdefault("id", str(uuid.uuid4()))
            current["tag"] = tag
            current["nombre"] = nombre
            return
        self._ubicaciones()[idx] = {"id": str(uuid.uuid4()), "tag": tag, "nombre": nombre}

    def delete_ubicacion(self, index) -> None:
        idx = self._require_index(index, self._ubicaciones(), "Seleccione una ubicacion")
        self._ubicaciones().pop(idx)

    # -------- gabinetes --------
    def add_gabinete(self, tag, nombre, ubic_tag) -> None:
        tag, nombre, ubic = self._validate_gabinete_data(tag, nombre, ubic_tag)
        ubic_tag_clean, ubic_nombre = self._sala_parts(ubic)
        label = self._sala_label(ubic_tag_clean, ubic_nombre)
        self._gabinetes().append(
            {
                "id": str(uuid.uuid4()),
                "tag": tag,
                "nombre": nombre,
                "sala": label,
                "ubicacion_id": self._clean_text(ubic.get("id")),
                "is_board": False,
                "components": [],
            }
        )

    def edit_gabinete(self, index, tag, nombre, ubic_tag) -> None:
        idx = self._require_index(index, self._gabinetes(), "Seleccione un gabinete")
        tag, nombre, ubic = self._validate_gabinete_data(tag, nombre, ubic_tag, skip_index=idx)
        current = self._gabinetes()[idx]
        if not isinstance(current, dict):
            current = {}
            self._gabinetes()[idx] = current
        current.setdefault("id", str(uuid.uuid4()))
        ubic_tag_clean, ubic_nombre = self._sala_parts(ubic)
        current["tag"] = tag
        current["nombre"] = nombre
        current["sala"] = self._sala_label(ubic_tag_clean, ubic_nombre)
        current["ubicacion_id"] = self._clean_text(ubic.get("id"))
        current.setdefault("is_board", False)
        current.setdefault("components", [])

    def delete_gabinete(self, index) -> None:
        idx = self._require_index(index, self._gabinetes(), "Seleccione un gabinete")
        self._gabinetes().pop(idx)

    def update_gabinete_field(self, index, field, value) -> None:
        idx = self._require_index(index, self._gabinetes(), "Seleccione un gabinete")
        cabinet = self._gabinetes()[idx]
        if not isinstance(cabinet, dict):
            cabinet = {}
            self._gabinetes()[idx] = cabinet

        field_name = self._clean_text(field)
        if field_name not in {"tag", "nombre", "sala", "is_board", "is_energy_source"}:
            raise ValueError(f"Campo de gabinete invalido: {field_name}")

        if field_name in {"tag", "nombre", "sala"}:
            text_value = self._clean_text(value)
            if not text_value:
                raise ValueError("Complete todos los campos")
            if field_name == "tag":
                for i, gab in enumerate(self._gabinetes()):
                    if i == idx or not isinstance(gab, dict):
                        continue
                    if self._clean_text(gab.get("tag")) == text_value:
                        raise ValueError("TAG ya existe")
            cabinet[field_name] = text_value
            if field_name == "sala":
                ubic = self._find_ubicacion_by_label_or_tag(text_value)
                if ubic is not None:
                    cabinet["ubicacion_id"] = self._clean_text(ubic.get("id"))
            return

        cabinet[field_name] = bool(value)

