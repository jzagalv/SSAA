# -*- coding: utf-8 -*-
"""Persistence helpers for Bank/Charger screen."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from PyQt5.QtCore import Qt


CODE_LAL = "L(AL)"


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

    def get_saved_perfil_cargas(self) -> List[Dict[str, Any]]:
        """Read profile preferring bank_charger.*, fallback to root legacy."""
        proyecto = self._proyecto()
        cfg = proyecto.get("bank_charger", None)
        if isinstance(cfg, dict):
            perfil_bc = cfg.get("perfil_cargas", None)
            if isinstance(perfil_bc, list) and perfil_bc:
                return perfil_bc
        perfil_root = proyecto.get("perfil_cargas", None)
        if isinstance(perfil_root, list):
            return perfil_root
        return []

    def get_saved_random_loads(self) -> Dict[str, Any]:
        """Read random-load data preferring bank_charger.*, fallback to root/profile."""
        proyecto = self._proyecto()
        cfg = proyecto.get("bank_charger", None)
        if isinstance(cfg, dict):
            rnd_bc = cfg.get("cargas_aleatorias", None)
            if isinstance(rnd_bc, dict) and rnd_bc:
                return rnd_bc
        rnd_root = proyecto.get("cargas_aleatorias", None)
        if isinstance(rnd_root, dict) and rnd_root:
            return rnd_root
        perfil = self.get_saved_perfil_cargas()
        rnd = self.extract_random_loads_from_perfil(perfil)
        return rnd if isinstance(rnd, dict) else {}

    @staticmethod
    def _stable_dump(value: Any) -> str:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)

    @staticmethod
    def _to_number_or_str(text: str) -> Any:
        txt = (text or "").strip()
        if not txt or txt in ("-", "—", "â€”"):
            return ""
        txt2 = txt.replace(",", ".")
        try:
            return float(txt2)
        except ValueError:
            return txt

    @staticmethod
    def _is_lal_code(code: Any) -> bool:
        return str(code or "").strip().upper() == CODE_LAL

    @staticmethod
    def extract_random_loads_from_perfil(perfil_rows: Any) -> Dict[str, Any]:
        """Derive random-load row from profile list (L(al))."""
        if not isinstance(perfil_rows, list):
            return {}
        for row in perfil_rows:
            if not isinstance(row, dict):
                continue
            if BankChargerPersistence._is_lal_code(row.get("item", "")):
                return {
                    "item": row.get("item", "L(al)"),
                    "desc": row.get("desc", "Cargas Aleatorias"),
                    "p": row.get("p", ""),
                    "i": row.get("i", ""),
                    "t_inicio": row.get("t_inicio", ""),
                    "duracion": row.get("duracion", ""),
                }
        return {}

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

            row: Dict[str, Any] = {
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
                row["scenario_id"] = scenario_id
            perfil.append(row)
        return perfil

    def collect_random_loads(self, perfil_rows: Any = None) -> Dict[str, Any]:
        """Read random-load row from profile rows."""
        perfil = perfil_rows if isinstance(perfil_rows, list) else self.collect_perfil_cargas()
        return self.extract_random_loads_from_perfil(perfil)

    def is_perfil_storage_synced(
        self,
        perfil_rows: List[Dict[str, Any]],
        random_loads: Dict[str, Any] | None = None,
    ) -> bool:
        """Check if canonical+legacy mirrors already match the provided values."""
        proyecto = self._proyecto()
        cfg = proyecto.get("bank_charger", {})
        if not isinstance(cfg, dict):
            return False

        rnd = random_loads if isinstance(random_loads, dict) else self.collect_random_loads(perfil_rows)
        checks = [
            self._stable_dump(cfg.get("perfil_cargas", [])) == self._stable_dump(perfil_rows),
            self._stable_dump(proyecto.get("perfil_cargas", [])) == self._stable_dump(perfil_rows),
            self._stable_dump(cfg.get("cargas_aleatorias", {})) == self._stable_dump(rnd),
            self._stable_dump(proyecto.get("cargas_aleatorias", {})) == self._stable_dump(rnd),
        ]
        return all(checks)

    def save_perfil_cargas(
        self,
        perfil_rows: List[Dict[str, Any]] | None = None,
        random_loads: Dict[str, Any] | None = None,
    ) -> None:
        """Persist profile rows and random-loads in canonical + legacy mirrors."""
        scr = self.screen
        proyecto = self._proyecto()
        cfg = self.get_proyecto_data()

        perfil = perfil_rows if isinstance(perfil_rows, list) else self.collect_perfil_cargas()
        rnd = random_loads if isinstance(random_loads, dict) else self.collect_random_loads(perfil)

        idx: Dict[str, Any] = {}
        for row in perfil:
            if not isinstance(row, dict):
                continue
            key = scr._norm_code(row.get("item", ""))
            if key:
                idx[key] = row

        # Canonical location
        cfg["perfil_cargas"] = perfil
        cfg["perfil_cargas_idx"] = idx
        cfg["cargas_aleatorias"] = dict(rnd)

        # Legacy mirror (compatibility)
        proyecto["perfil_cargas"] = perfil
        proyecto["perfil_cargas_idx"] = idx
        proyecto["cargas_aleatorias"] = dict(rnd)

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
