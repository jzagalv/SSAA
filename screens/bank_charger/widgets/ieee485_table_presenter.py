# -*- coding: utf-8 -*-
"""IEEE 485 worksheet table presenter.

This module extracts the *rendering* of the IEEE 485 "Cell sizing worksheet"
table from the Bank/Charger sizing screen.

Notes
-----
- The presenter depends on PyQt5 widgets, but avoids any domain calculations.
- Formatting + storage helpers remain on the screen object (e.g. _set_ro_cell,
  _set_kt_cell, _kt_for_key, _set_section_header_row, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableWidgetItem


@dataclass
class IEEE485Period:
    A: float
    M: float

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "IEEE485Period":
        return IEEE485Period(A=float(d.get("A", 0.0)), M=float(d.get("M", 0.0)))


class IEEE485TablePresenter:
    def __init__(self, screen):
        self.screen = screen

    def update(self) -> None:
        """Render the IEEE 485 worksheet table from the current duty cycle cache."""

        scr = self.screen

        periods_raw = list(scr._cycle_periods_cache) if getattr(scr, "_cycle_periods_cache", None) else []
        rnd = getattr(scr, "_cycle_random_cache", None)

        scr._updating = True
        try:
            scr.tbl_ieee.setRowCount(0)
            scr.tbl_ieee.clearSpans()

            if not periods_raw:
                return

            periods: List[IEEE485Period] = [IEEE485Period.from_dict(p) for p in periods_raw]
            A = [p.A for p in periods]
            M = [p.M for p in periods]
            n = len(periods)

            def A_i(i: int) -> float:
                return 0.0 if i <= 0 else A[i - 1]

            def M_i(i: int) -> float:
                return M[i - 1]

            # Row count: for each section sec: header + sec period rows + SubTot + Total => sec+3
            total_rows = sum((sec + 3) for sec in range(1, n + 1))
            if rnd:
                total_rows += 2  # header + random row
            scr.tbl_ieee.setRowCount(total_rows)

            row = 0

            for sec in range(1, n + 1):
                # Section header
                if sec < n:
                    hdr = (
                        f"Sección {sec} - Primero(s) {sec} Periodos - "
                        f"Si A{sec+1} es mayor que A{sec}, ir a la sección {sec+1}."
                    )
                else:
                    hdr = f"Sección {sec} - Primero(s) {sec} Periodos."
                scr._set_section_header_row(row, hdr)
                row += 1

                # Rows 1..sec
                for i in range(1, sec + 1):
                    Ai = A_i(i)
                    A_prev = A_i(i - 1)
                    dA = Ai - A_prev
                    Mi = M_i(i)
                    T = sum(M[j - 1] for j in range(i, sec + 1))

                    key = f"S{sec}_P{i}"
                    kt_val = scr._kt_for_key(key, "")

                    # Default Kt rules (legacy behavior)
                    if kt_val in ("", None):
                        try:
                            if 470 <= float(T) <= 480:
                                kt_val = 7.99
                            elif 1 <= float(T) <= 5:
                                kt_val = 0.02
                        except Exception:
                            import logging
                            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

                    try:
                        kt_float = (
                            float(str(kt_val).replace(",", "."))
                            if kt_val not in ("", None)
                            else None
                        )
                    except Exception:
                        kt_float = None

                    pos = dA * kt_float if (kt_float is not None and dA > 0) else (0.0 if kt_float is not None else "")
                    neg = dA * kt_float if (kt_float is not None and dA < 0) else (0.0 if kt_float is not None else "")

                    scr._set_ro_cell(row, 0, str(i), role_key=key)
                    scr._set_ro_cell(row, 1, f"A{i}={Ai:.2f}")
                    scr._set_ro_cell(row, 2, f"A{i}−A{i-1}={dA:.2f}")
                    scr._set_ro_cell(row, 3, f"M{i}={Mi:.0f}")
                    scr._set_ro_cell(
                        row,
                        4,
                        f"T= {'+'.join([f'M{j}' for j in range(i, sec+1)])} = {T:.0f}",
                    )
                    scr._set_kt_cell(row, key, kt_val)
                    scr._set_ro_cell(row, 6, f"{pos:.2f}" if pos != "" else "")
                    scr._set_ro_cell(row, 7, f"{neg:.2f}" if neg != "" else "")
                    row += 1

                # Sub Tot row
                pos_sum = 0.0
                neg_sum = 0.0
                kt_missing = False
                for i in range(1, sec + 1):
                    key = f"S{sec}_P{i}"
                    kt_val = scr._kt_for_key(key, "")
                    try:
                        kt_float = (
                            float(str(kt_val).replace(",", "."))
                            if kt_val not in ("", None, "")
                            else None
                        )
                    except Exception:
                        kt_float = None
                    if kt_float is None:
                        kt_missing = True
                        continue
                    dA = A_i(i) - A_i(i - 1)
                    if dA > 0:
                        pos_sum += dA * kt_float
                    elif dA < 0:
                        neg_sum += dA * kt_float

                scr._set_ro_cell(row, 0, "Sec")
                scr._set_ro_cell(row, 1, str(sec))
                scr._set_span_with_placeholders(scr.tbl_ieee, row, 2, 1, 4)
                it = QTableWidgetItem("Sub Tot")
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                scr.tbl_ieee.setItem(row, 2, it)
                scr._set_ro_cell(row, 6, "" if kt_missing else f"{pos_sum:.2f}")
                scr._set_ro_cell(row, 7, "" if kt_missing else f"{neg_sum:.2f}")
                row += 1

                # Total row
                scr._set_ro_cell(row, 0, "Total")
                scr._set_span_with_placeholders(scr.tbl_ieee, row, 0, 1, 6)
                it2 = scr.tbl_ieee.item(row, 0)
                it2.setText("Total")
                it2.setFlags(it2.flags() & ~Qt.ItemIsEditable)

                net = "" if kt_missing else (pos_sum + neg_sum)
                scr._set_ro_cell(row, 6, "" if net == "" else f"{net:.2f}")
                scr._set_ro_cell(row, 7, "***" if net != "" else "")
                row += 1

            # Random load section
            if rnd:
                scr._set_section_header_row(row, "Cargas Aleatorias (si es requerido)")
                row += 1
                AR = float(rnd.get("A", 0.0))
                MR = float(rnd.get("M", 0.0))
                dAR = AR - 0.0
                key = "R"
                kt_val = scr._kt_for_key(key, "")
                try:
                    kt_float = (
                        float(str(kt_val).replace(",", "."))
                        if kt_val not in ("", None)
                        else None
                    )
                except Exception:
                    kt_float = None
                pos = dAR * kt_float if (kt_float is not None and dAR > 0) else (0.0 if kt_float is not None else "")

                scr._set_ro_cell(row, 0, "A(al)", role_key=key)
                scr._set_ro_cell(row, 1, f"AR={AR:.0f}")
                scr._set_ro_cell(row, 2, f"AR−0={dAR:.0f}")
                scr._set_ro_cell(row, 3, f"MR={MR:.0f}")
                scr._set_ro_cell(row, 4, f"T=MR = {MR:.0f}")
                scr._set_kt_cell(row, key, kt_val)
                scr._set_ro_cell(row, 6, f"{pos:.1f}" if pos != "" else "")
                scr._set_ro_cell(row, 7, "***" if pos != "" else "")
                row += 1

            # Apply RO flags: all cells read-only except Kt column when role key present
            for r in range(scr.tbl_ieee.rowCount()):
                for c in range(scr.tbl_ieee.columnCount()):
                    it = scr.tbl_ieee.item(r, c)
                    if it is None:
                        it = QTableWidgetItem("")
                        scr.tbl_ieee.setItem(r, c, it)

                    if c == 5:
                        key = (
                            scr.tbl_ieee.item(r, 0).data(Qt.UserRole)
                            if scr.tbl_ieee.item(r, 0)
                            else None
                        )
                        if key:
                            it.setFlags(it.flags() | Qt.ItemIsEditable)
                        else:
                            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                    else:
                        it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            scr.tbl_ieee.resizeRowsToContents()
        finally:
            scr._updating = False
