# -*- coding: utf-8 -*-
"""Controller for Instalaciones screen (no PyQt dependency)."""

from __future__ import annotations

from services.installations_service import InstallationsService


class LocationController:
    def __init__(self, dm):
        self.dm = dm
        self.service = InstallationsService(dm)
        self._sync_aliases()

    def _mark_dirty(self) -> None:
        if hasattr(self.dm, "mark_dirty"):
            self.dm.mark_dirty(True)

    def _sync_aliases(self) -> None:
        if self.dm is None:
            return
        store = getattr(self.dm, "instalaciones", None)
        if not isinstance(store, dict):
            return
        if not isinstance(store.get("ubicaciones"), list):
            store["ubicaciones"] = list(store.get("ubicaciones") or [])
        if not isinstance(store.get("gabinetes"), list):
            store["gabinetes"] = list(store.get("gabinetes") or [])

        ubicaciones = store["ubicaciones"]
        gabinetes = store["gabinetes"]

        if getattr(self.dm, "ubicaciones", None) is not ubicaciones:
            self.dm.ubicaciones = ubicaciones
        if getattr(self.dm, "salas", None) is not ubicaciones:
            self.dm.salas = ubicaciones
        if getattr(self.dm, "gabinetes", None) is not gabinetes:
            self.dm.gabinetes = gabinetes

    def add_ubicacion(self, tag, nombre) -> None:
        self.service.add_ubicacion(tag, nombre)
        self._sync_aliases()
        self._mark_dirty()

    def edit_ubicacion(self, index, tag, nombre) -> None:
        self.service.edit_ubicacion(index, tag, nombre)
        self._sync_aliases()
        self._mark_dirty()

    def delete_ubicacion(self, index) -> None:
        self.service.delete_ubicacion(index)
        self._sync_aliases()
        self._mark_dirty()

    def add_gabinete(self, tag, nombre, ubic_tag) -> None:
        self.service.add_gabinete(tag, nombre, ubic_tag)
        self._sync_aliases()
        self._mark_dirty()

    def edit_gabinete(self, index, tag, nombre, ubic_tag) -> None:
        self.service.edit_gabinete(index, tag, nombre, ubic_tag)
        self._sync_aliases()
        self._mark_dirty()

    def delete_gabinete(self, index) -> None:
        self.service.delete_gabinete(index)
        self._sync_aliases()
        self._mark_dirty()

    def update_gabinete_field(self, index, field, value) -> None:
        self.service.update_gabinete_field(index, field, value)
        self._sync_aliases()
        self._mark_dirty()

    def update_gabinete_field_by_id(self, cab_id, field, value) -> None:
        self.service.update_gabinete_field_by_id(cab_id, field, value)
        self._sync_aliases()
        self._mark_dirty()

    def edit_gabinete_by_id(self, cab_id, tag, nombre, ubic_tag) -> None:
        self.service.edit_gabinete_by_id(cab_id, tag, nombre, ubic_tag)
        self._sync_aliases()
        self._mark_dirty()

    def delete_gabinete_by_id(self, cab_id) -> None:
        self.service.delete_gabinete_by_id(cab_id)
        self._sync_aliases()
        self._mark_dirty()
