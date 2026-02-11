# -*- coding: utf-8 -*-
"""Bank/Charger - Summary table presenter.

Este módulo contiene únicamente lógica de UI para poblar la tabla resumen
de equipos (banco de baterías / cargador) desde el proyecto.

La intención es mantener `bank_charger_controller.py` enfocado en orquestación
y cálculo, y dejar el renderizado de tablas en "presenters".
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QComboBox, QTableWidgetItem


class SummaryTablePresenter:
    def __init__(self, screen):
        self.screen = screen

    def update(self):
        """Puebla la tabla resumen de equipos (según definición en Proyecto)."""
        scr = self.screen
        proyecto = getattr(scr.data_model, "proyecto", {}) or {}

        ov = proyecto.get("bc_overrides", {}) if isinstance(proyecto.get("bc_overrides", {}), dict) else {}
        bundle = scr._get_bc_bundle()
        bank = getattr(bundle, "bank", None) if bundle is not None else None
        charger = getattr(bundle, "charger", None) if bundle is not None else None

        # Valores calculados / comerciales (formateo 2 decimales cuando aplica)
        bb_calc = getattr(bank, "ah_required", proyecto.get("bb_ah_calculada", 0) or 0)
        ch_calc = getattr(charger, "i_calc", proyecto.get("charger_a_calculada", 0) or 0)
        bb_com = getattr(bundle, "ah_commercial_str", None) or ov.get("bank_commercial_ah", proyecto.get("bb_ah_comercial", "—"))
        ch_com = getattr(bundle, "i_charger_commercial_str", None) or ov.get("charger_commercial_a", proyecto.get("charger_a_comercial", "—"))

        def _fmt2(v):
            try:
                return f"{float(v):.2f}"
            except Exception:
                return str(v)

        bb_calc_str = _fmt2(bb_calc)
        ch_calc_str = _fmt2(ch_calc)
        bb_com_str = _fmt2(bb_com) if bb_com not in ("—", "", None) else "—"
        ch_com_str = _fmt2(ch_com) if ch_com not in ("—", "", None) else "—"

        # Cantidades
        num_bancos = proyecto.get("num_bancos", 1) or 1
        num_carg = proyecto.get("num_cargadores", 1) or 1
        try:
            num_bancos = int(num_bancos)
        except Exception:
            num_bancos = 1
        try:
            num_carg = int(num_carg)
        except Exception:
            num_carg = 1
        num_bancos = max(0, num_bancos)
        num_carg = max(0, num_carg)

        # Opciones TAG desde gabinetes marcados como Fuente de Energía
        tags = []
        for g in getattr(scr.data_model, "gabinetes", []) or []:
            if isinstance(g, dict) and g.get("is_energy_source", False):
                t = str(g.get("tag", "")).strip()
                if t:
                    tags.append(t)
        tags = sorted(set(tags))

        equip_tags = proyecto.get("equip_tags", {})
        if not isinstance(equip_tags, dict):
            equip_tags = {}

        rows = []
        for i in range(1, num_bancos + 1):
            rows.append((f"Banco de Baterías N°{i}", f"BBAT{i}", bb_calc_str, bb_com_str))
        for i in range(1, num_carg + 1):
            rows.append((f"Cargador de Baterías N°{i}", f"CBAT{i}", ch_calc_str, ch_com_str))

        scr.tbl_summary.blockSignals(True)
        try:
            scr.tbl_summary.setRowCount(len(rows))
            for r, (nombre, key, calc, com) in enumerate(rows):
                # Col 0: Equipo
                it0 = QTableWidgetItem(nombre)
                it0.setFlags(it0.flags() & ~Qt.ItemIsEditable)
                scr.tbl_summary.setItem(r, 0, it0)

                # Col 1: TAG (combobox)
                cb = QComboBox()
                cb.addItem("")
                for t in tags:
                    cb.addItem(t)

                # preselección
                selected = equip_tags.get(key, "")
                if not selected:
                    prefix = "BBAT" if key.startswith("BBAT") else "CBAT"
                    want = f"{prefix}{key[len(prefix):]}"
                    if want in tags:
                        selected = want
                    else:
                        for t in tags:
                            if t.upper().startswith(prefix):
                                selected = t
                                break
                if selected and selected in tags:
                    cb.setCurrentText(selected)

                cb.currentTextChanged.connect(lambda val, k=key: scr._on_summary_tag_changed(k, val))
                scr.tbl_summary.setCellWidget(r, 1, cb)

                # Col 2-3: valores
                it2 = QTableWidgetItem(calc)
                it2.setFlags(it2.flags() & ~Qt.ItemIsEditable)
                it3 = QTableWidgetItem(com)
                it3.setFlags(it3.flags() & ~Qt.ItemIsEditable)
                scr.tbl_summary.setItem(r, 2, it2)
                scr.tbl_summary.setItem(r, 3, it3)
        finally:
            scr.tbl_summary.blockSignals(False)

        scr.tbl_summary.resizeRowsToContents()
        return True

        scr.tbl_summary.resizeRowsToContents()
