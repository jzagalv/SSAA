# -*- coding: utf-8 -*-
"""Persistencia específica de la pantalla Bank/Charger.

Este módulo concentra toda la lectura/escritura del "proyecto" (data_model.proyecto)
relacionada con:

- Perfil de cargas (tbl_cargas)
- Kt IEEE 485 (tbl_ieee)

Así se evita mezclar I/O con lógica de UI/orquestación.
"""

from __future__ import annotations

from typing import Any, Dict

from PyQt5.QtCore import Qt


class BankChargerPersistence:
    """Encapsula operaciones de persistencia del proyecto para Bank/Charger."""

    def __init__(self, screen: Any):
        self.screen = screen

    def _proyecto(self) -> Dict[str, Any]:
        scr = self.screen
        return getattr(scr.data_model, "proyecto", {}) or {}

    @staticmethod
    def _to_number_or_str(text: str) -> Any:
        txt = (text or "").strip()
        if not txt or txt == "—":
            return ""
        txt2 = txt.replace(",", ".")
        try:
            return float(txt2)
        except ValueError:
            return txt

    def save_perfil_cargas(self) -> None:
        """Lee tbl_cargas y guarda en proyecto['perfil_cargas'] + índice normalizado."""
        scr = self.screen
        proyecto = self._proyecto()

        perfil = []
        for r in range(scr.tbl_cargas.rowCount()):
            def cell_text(c: int) -> str:
                it = scr.tbl_cargas.item(r, c)
                return it.text().strip() if it else ""

            item = cell_text(0)
            desc = cell_text(1)
            if not item and not desc:
                continue

            fila = {
                "item": item,
                "desc": desc,
                "p": self._to_number_or_str(cell_text(2)),
                "i": self._to_number_or_str(cell_text(3)),
                "t_inicio": self._to_number_or_str(cell_text(4)),
                "duracion": self._to_number_or_str(cell_text(5)),
            }
            perfil.append(fila)

        proyecto["perfil_cargas"] = perfil

        # Índice por código normalizado (para búsquedas rápidas / consistencia)
        idx: Dict[str, Any] = {}
        for row in perfil:
            k = scr._norm_code(row.get("item", ""))
            if not k:
                continue
            idx[k] = row
        proyecto["perfil_cargas_idx"] = idx

        if hasattr(scr.data_model, "mark_dirty"):
            scr.data_model.mark_dirty(True)

    def save_ieee485_kt(self) -> None:
        """Lee columna Kt en tbl_ieee y guarda en proyecto['ieee485_kt']."""
        scr = self.screen
        store = scr._get_ieee_kt_store()

        for r in range(scr.tbl_ieee.rowCount()):
            key_item = scr.tbl_ieee.item(r, 0)
            if key_item is None:
                continue
            key = key_item.data(Qt.UserRole)
            if not key:
                continue

            kt_item = scr.tbl_ieee.item(r, 5)
            if kt_item is None:
                continue

            txt = (kt_item.text() or "").strip().replace(",", ".")
            try:
                kt = float(txt) if txt else ""
            except Exception:
                kt = ""
            store[str(key)] = kt

        if hasattr(scr.data_model, "mark_dirty"):
            scr.data_model.mark_dirty(True)
