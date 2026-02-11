# -*- coding: utf-8 -*-
"""Persistence helpers for Bank/Charger screen."""

from __future__ import annotations

from typing import Any, Dict, List

from PyQt5.QtCore import Qt


class BankChargerPersistence:
    """Encapsulate project read/write operations for Bank/Charger."""

    def __init__(self, screen: Any):
        self.screen = screen

    def _proyecto(self) -> Dict[str, Any]:
        scr = self.screen
        dm = getattr(scr, "data_model", None)
        proyecto = getattr(dm, "proyecto", None)
        if not isinstance(proyecto, dict):
            proyecto = {}
            if dm is not None:
                dm.proyecto = proyecto
        return proyecto

    def get_proyecto_data(self) -> Dict[str, Any]:
        """Return canonical bank_charger storage dict inside project."""
        proyecto = self._proyecto()
        cfg = proyecto.get("bank_charger", None)
        if not isinstance(cfg, dict):
            cfg = {}
            proyecto["bank_charger"] = cfg
        return cfg

    @staticmethod
    def _to_number_or_str(text: str) -> Any:
        txt = (text or "").strip()
        if not txt or txt in ("—", "â€”"):
            return ""
        txt2 = txt.replace(",", ".")
        try:
            return float(txt2)
        except ValueError:
            return txt

    def collect_perfil_cargas(self) -> List[Dict[str, Any]]:
        """Read tbl_cargas and return serialized profile rows."""
        scr = self.screen
        perfil: List[Dict[str, Any]] = []
        for r in range(scr.tbl_cargas.rowCount()):
            def cell_text(c: int) -> str:
                it = scr.tbl_cargas.item(r, c)
                return it.text().strip() if it else ""

            item = cell_text(0)
            desc = cell_text(1)
            if not item and not desc:
                continue

            fila: Dict[str, Any] = {
                "item": item,
                "desc": desc,
                "p": self._to_number_or_str(cell_text(2)),
                "i": self._to_number_or_str(cell_text(3)),
                "t_inicio": self._to_number_or_str(cell_text(4)),
                "duracion": self._to_number_or_str(cell_text(5)),
            }
            it_desc = scr.tbl_cargas.item(r, 1)
            scenario_id = None
            if it_desc is not None:
                sid = it_desc.data(Qt.UserRole)
                if sid not in (None, ""):
                    try:
                        scenario_id = int(sid)
                    except Exception:
                        scenario_id = sid
            if scenario_id is None and hasattr(scr, "_extract_scenario_id"):
                try:
                    scenario_id = scr._extract_scenario_id(desc)
                except Exception:
                    scenario_id = None
            if scenario_id is not None:
                fila["scenario_id"] = scenario_id
            perfil.append(fila)
        return perfil

    def save_perfil_cargas(self, perfil: List[Dict[str, Any]] | None = None) -> None:
        """Persist profile rows in proyecto['bank_charger']['perfil_cargas']."""
        scr = self.screen
        cfg = self.get_proyecto_data()
        perfil_to_save = perfil if isinstance(perfil, list) else self.collect_perfil_cargas()
        cfg["perfil_cargas"] = perfil_to_save

        idx: Dict[str, Any] = {}
        for row in perfil_to_save:
            if not isinstance(row, dict):
                continue
            k = scr._norm_code(row.get("item", ""))
            if not k:
                continue
            idx[k] = row
        cfg["perfil_cargas_idx"] = idx

    def get_ieee485_kt_data(self) -> Dict[str, Any]:
        """Return persisted IEEE485 Kt mapping from root project dict."""
        proyecto = self._proyecto()
        store = proyecto.get("ieee485_kt", None)
        return store if isinstance(store, dict) else {}

    def collect_ieee485_kt(self) -> Dict[str, Any]:
        """Read Kt column from tbl_ieee and return serialized mapping."""
        scr = self.screen
        data: Dict[str, Any] = {}
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
            data[str(key)] = kt
        return data

    def save_ieee485_kt(self, data: Dict[str, Any] | None = None) -> None:
        """Persist IEEE485 Kt mapping in proyecto['ieee485_kt']."""
        proyecto = self._proyecto()
        data_to_save = data if isinstance(data, dict) else self.collect_ieee485_kt()
        proyecto["ieee485_kt"] = dict(data_to_save)
