# -*- coding: utf-8 -*-
"""
domain/battery.py

Cálculos de ventana de voltaje y número de celdas para banco DC.
- No depende de PyQt.
- No inventa 0: si falta un dato relevante, retorna issues.
- Interpreta min_voltaje_cc / max_voltaje_cc como porcentajes respecto a tensión_nominal.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from .parse import to_float

@dataclass
class Issue:
    level: str   # "error" | "warn" | "info"
    field: str   # clave esperada en proyecto u otro
    message: str


@dataclass
class BatterySizingResult:
    ok: bool
    v_nominal: Optional[float]
    v_min: Optional[float]
    v_max: Optional[float]

    # parámetros de celda
    v_cell_float: Optional[float]
    num_cells_user: Optional[int]

    # resultados
    n_cells_calc_min: Optional[int]
    n_cells_calc_max: Optional[int]
    n_cells_recommended: Optional[int]  # si hay user => user, si no => promedio redondeado

    issues: List[Issue]

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
        # preferimos redondear en vez de truncar silenciosamente
        return int(round(v))
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(float(s.replace(",", ".")))
    except Exception:
        return None


def battery_window_and_cells(proyecto: Dict[str, Any]) -> BatterySizingResult:
    """
    Interpreta datos del proyecto (ya normalizados idealmente) y calcula:
    - Vmin/Vmax absolutos desde % (si hay tensión_nominal y %)
    - N mín/máx de celdas por ventana de Vmin/Vmax
    - N recomendado
    """
    issues: List[Issue] = []

    v_nom = to_float(proyecto.get("tension_nominal"))

    min_pct = to_float(proyecto.get("min_voltaje_cc"))
    max_pct = to_float(proyecto.get("max_voltaje_cc"))

    # Validación de porcentajes si vienen
    if min_pct is not None and not (0.0 <= min_pct <= 100.0):
        issues.append(Issue("error", "min_voltaje_cc", "El % mínimo debe estar entre 0 y 100."))
    if max_pct is not None and not (0.0 <= max_pct <= 100.0):
        issues.append(Issue("error", "max_voltaje_cc", "El % máximo debe estar entre 0 y 100."))

    # Si vienen ya calculados (v_min/v_max) los podemos usar como fallback,
    # pero si hay v_nom + % preferimos recalcular siempre para consistencia.
    v_min_abs = to_float(proyecto.get("v_min"))
    v_max_abs = to_float(proyecto.get("v_max"))

    # Preferencia: calcular desde v_nom y % si están disponibles
    if v_nom is not None and min_pct is not None:
        v_min_abs = v_nom * (1.0 - min_pct / 100.0)
    if v_nom is not None and max_pct is not None:
        v_max_abs = v_nom * (1.0 + max_pct / 100.0)

    v_min = v_min_abs
    v_max = v_max_abs

    v_cell = to_float(proyecto.get("tension_flotacion_celda"))
    n_user = _as_int(proyecto.get("num_celdas_usuario"))

    # Validaciones mínimas (sin inventar valores)
    if v_nom is None:
        issues.append(Issue("error", "tension_nominal", "Falta tensión nominal del sistema DC."))
    if v_min is None:
        issues.append(Issue("error", "min_voltaje_cc", "Falta voltaje mínimo permitido del sistema DC."))
    if v_max is None:
        issues.append(Issue("error", "max_voltaje_cc", "Falta voltaje máximo permitido del sistema DC."))
    if v_cell is None:
        issues.append(Issue("error", "tension_flotacion_celda", "Falta tensión de flotación por celda."))

    if v_min is not None and v_max is not None and v_min > v_max:
        issues.append(Issue("error", "min_voltaje_cc/max_voltaje_cc", "Vmin es mayor que Vmax."))

    if v_cell is not None and v_cell <= 0:
        issues.append(Issue("error", "tension_flotacion_celda", "La tensión de celda debe ser > 0."))

    if n_user is not None and n_user <= 0:
        issues.append(Issue("error", "num_celdas_usuario", "El número de celdas debe ser > 0."))

    # Si hay errores críticos, no calculamos
    has_error = any(i.level == "error" for i in issues)
    if has_error:
        return BatterySizingResult(
            ok=False,
            v_nominal=v_nom, v_min=v_min, v_max=v_max,
            v_cell_float=v_cell,
            num_cells_user=n_user,
            n_cells_calc_min=None,
            n_cells_calc_max=None,
            n_cells_recommended=n_user if n_user else None,
            issues=issues
        )

    # Cálculo por ventana:
    # Nmin = ceil(Vmin / Vcell), Nmax = floor(Vmax / Vcell)
    import math
    n_min = int(math.ceil(v_min / v_cell))   # type: ignore[arg-type]
    n_max = int(math.floor(v_max / v_cell))  # type: ignore[arg-type]

    if n_min <= 0 or n_max <= 0:
        issues.append(Issue("error", "voltajes", "Cálculo inválido de número de celdas (<=0)."))

    if n_min > n_max:
        issues.append(Issue("error", "voltajes", "La ventana de voltaje no permite un número de celdas válido (Nmin > Nmax)."))

    has_error = any(i.level == "error" for i in issues)
    if has_error:
        return BatterySizingResult(
            ok=False,
            v_nominal=v_nom, v_min=v_min, v_max=v_max,
            v_cell_float=v_cell,
            num_cells_user=n_user,
            n_cells_calc_min=n_min,
            n_cells_calc_max=n_max,
            n_cells_recommended=n_user if n_user else None,
            issues=issues
        )

    # recomendado
    if n_user is not None:
        n_rec = n_user
        if not (n_min <= n_user <= n_max):
            issues.append(Issue("warn", "num_celdas_usuario",
                                f"El valor ingresado ({n_user}) está fuera de ventana [{n_min}, {n_max}]."))
    else:
        n_rec = int(round((n_min + n_max) / 2.0))

    return BatterySizingResult(
        ok=True,
        v_nominal=v_nom, v_min=v_min, v_max=v_max,
        v_cell_float=v_cell,
        num_cells_user=n_user,
        n_cells_calc_min=n_min,
        n_cells_calc_max=n_max,
        n_cells_recommended=n_rec,
        issues=issues
    )
