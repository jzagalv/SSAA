# -*- coding: utf-8 -*-
"""Persistencia y acceso a datos para la pantalla Cabinet/Consumos.

Este módulo concentra:
- Lectura del catálogo de consumos (preferencia: librería .lib cargada por el usuario).
- Marcado de 'dirty' en el modelo.
- Utilidades para acceso a gabinetes (sin lógica de UI).

Nota: Mantener este archivo libre de Qt para evitar acoplamiento con la UI.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class CabinetPersistence:
    data_model: Any
    component_db_file: str

    def load_component_database(self) -> List[Dict[str, Any]]:
        """Retorna el catálogo de consumos.

        Prioridad:
        1) Librería .lib de consumos cargada por el usuario (DataModel.library_data['consumos']).
        2) Fallback legacy: resources/component_database.json (si existe).
        """
        # 1) Librería .lib (recomendada)
        try:
            lib = getattr(self.data_model, "library_data", {}) or {}
            lib = lib.get("consumos")
            if isinstance(lib, dict) and lib.get("file_type") == "SSAA_LIB_CONSUMOS":
                items = lib.get("items", [])
                if isinstance(items, list):
                    return items
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        # 2) Legacy JSON
        try:
            if not os.path.exists(self.component_db_file):
                return []
            with open(self.component_db_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            comps = data.get("components", [])
            return comps if isinstance(comps, list) else []
        except Exception as e:
            print("Error al leer catálogo de consumos:", e)
            return []

    def get_cabinets(self) -> List[Dict[str, Any]]:
        return getattr(self.data_model, "gabinetes", []) or []

    def mark_dirty(self, is_dirty: bool = True) -> None:
        if hasattr(self.data_model, "mark_dirty"):
            try:
                self.data_model.mark_dirty(is_dirty)
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
