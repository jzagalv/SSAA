# -*- coding: utf-8 -*-
"""
services/calculations.py

Fachada única para cálculos.
Meta: que la UI llame a *un solo lugar* para recalcular y validar.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

from domain.battery import battery_window_and_cells, BatterySizingResult


def compute_battery_sizing(project_dict: Dict[str, Any]) -> BatterySizingResult:
    """
    API nueva recomendada:
    - Acepta data_model.to_dict() o data_model.proyecto
    - Retorna BatterySizingResult con ok + issues
    """
    proy = project_dict.get("proyecto", project_dict)  # permite pasar proy directo
    return battery_window_and_cells(proy)


def compute_voltage_and_cells(
    proyecto: Dict[str, Any],
    v_cell_float: Optional[float] = None,
    num_cells_user: Optional[int] = None,
) -> Dict[str, Optional[float]]:
    """
    Wrapper de compatibilidad (Etapa 1):
    Mantiene una salida tipo dict para pantallas antiguas,
    pero calculando desde domain (una sola verdad).
    """
    # Si el caller pasa v_cell_float explícito, lo metemos temporalmente en proyecto
    # (sin ensuciar el dict original)
    proy = dict(proyecto or {})
    if v_cell_float is not None:
        proy["tension_flotacion_celda"] = v_cell_float
    if num_cells_user is not None:
        proy["num_celdas_usuario"] = num_cells_user

    res = battery_window_and_cells(proy)

    # Salida estilo "legacy-friendly":
    return {
        "v_nominal": res.v_nominal,
        "v_min": res.v_min,
        "v_max": res.v_max,
        "n_min": res.n_cells_calc_min,
        "n_max": res.n_cells_calc_max,
        "n_rec": res.n_cells_recommended,
        # opcional: para que la UI pueda mostrar mensajes sin reescribir todo
        "ok": 1.0 if res.ok else 0.0,
    }


def compute_all(project_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placeholder etapa 1: en el futuro orquesta todo.
    Hoy no modifica.
    """
    return project_dict
