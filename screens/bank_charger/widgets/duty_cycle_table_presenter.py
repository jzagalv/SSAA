# -*- coding: utf-8 -*-
"""Presenter de la tabla "Ciclo de trabajo" (duty cycle) para Bank/Charger."""

from __future__ import annotations

from typing import Dict, List, Optional

CODE_LAL = "L(al)"


class DutyCycleTablePresenter:
    """Renderiza la tabla de duty cycle y mantiene caches en el screen."""

    def __init__(self, screen):
        self.screen = screen

    def update(self) -> None:
        """Recalcula la tabla 'Ciclo de trabajo' (A1..An + A(al) si existe)."""
        scr = self.screen
        det, rnd = scr._extract_segments()

        scr.tbl_cycle.setRowCount(0)
        scr._cycle_periods_cache = []
        if not det:
            scr._cycle_random_cache = None
            return

        # Breakpoints (tiempos donde cambia el conjunto de cargas activas)
        bps = set()
        for seg in det:
            bps.add(float(seg["t0"]))
            bps.add(float(seg["t1"]))
        bps = sorted(bps)
        if len(bps) < 2:
            scr._cycle_random_cache = None
            return

        periods: List[Dict] = []
        for a, b in zip(bps[:-1], bps[1:]):
            if b <= a:
                continue
            mid = (a + b) / 2.0
            active = [seg for seg in det if seg["t0"] <= mid < seg["t1"]]
            if not active:
                continue

            active_codes = sorted({seg["code"] for seg in active}, key=scr._cycle_sort_key)
            total_i = sum(seg["I"] for seg in active)

            periods.append({
                "loads": " + ".join(active_codes),
                "total_i": float(total_i),
                "dur": float(b - a),
                "t0": float(a),
                "t1": float(b),
            })

        # Compactar periodos consecutivos con misma combinación de cargas
        compact: List[Dict] = []
        for p in periods:
            if compact and compact[-1]["loads"] == p["loads"] and abs(compact[-1]["t1"] - p["t0"]) < 1e-9:
                compact[-1]["dur"] += p["dur"]
                compact[-1]["t1"] = p["t1"]
                compact[-1]["total_i"] = p["total_i"]
            else:
                compact.append(dict(p))

        # Tabla: A1..An (+ A(al) al final si existe)
        scr.tbl_cycle.setRowCount(len(compact) + (1 if rnd else 0))

        for idx, p in enumerate(compact, start=1):
            label = f"A{idx}"
            scr._set_table_row_ro(
                scr.tbl_cycle, idx - 1,
                [label, p["loads"], f"{p['total_i']:.2f}", f"{p['dur']:.0f}"]
            )
            scr._cycle_periods_cache.append({
                "label": label,
                "A": p["total_i"],
                "M": p["dur"],
                "loads": p["loads"],
                "t0": p["t0"],
                "t1": p["t1"],
            })

        if rnd:
            r = len(compact)
            label = "A(al)"
            scr._set_table_row_ro(
                scr.tbl_cycle, r,
                [label, CODE_LAL, f"{rnd['I']:.2f}", f"{rnd['dur']:.0f}"]
            )
            scr._cycle_random_cache = {
                "label": label,
                "A": float(rnd["I"]),
                "M": float(rnd["dur"]),
                "t0": float(rnd["t0"]),
                "t1": float(rnd["t1"]),
            }
        else:
            scr._cycle_random_cache = None
