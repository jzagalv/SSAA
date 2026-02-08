
# -*- coding: utf-8 -*-
"""screens/load_tables/screen.py

Pantalla: Cuadros de carga
- Subpestaña CA: dos cuadros (Esencial / No esencial)
- Subpestaña CC: dos cuadros (Barra 1 / Barra 2)

Reglas:
1) El usuario elige el tablero (nodo de topología) por cuadro.
2) Si no hay datos, el cuadro no se muestra.
3) Cada fila es un nodo de salida (CARGA) y si hay cascada se suman consumos (alcance del tablero).
4) Estructura de columnas inspirada en las planillas entregadas (valores no disponibles quedan '-').
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QComboBox, QTableWidget, QTableWidgetItem, QGroupBox, QSizePolicy, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLineEdit, QDoubleSpinBox
import re
from screens.base import ScreenBase
from app.sections import Section
from core.keys import ProjectKeys as K
from ui.common.state import save_header_state, restore_header_state
from ui.utils.table_utils import configure_table_autoresize


from services.load_tables_engine import (
    list_board_nodes, build_ac_table, build_cc_table
)


# Opciones seleccionables (usuario)
MCB_OPTIONS = [
    "1x6A", "1x10A", "1x16A", "1x20A", "1x25A", "1x32A",
    "2x10A", "2x16A", "2x20A", "2x25A", "2x32A",
    "3x10A", "3x16A", "3x20A", "3x25A", "3x32A",
    "4x25A", "4x32A",
]
PHASE_OPTIONS = ["R", "S", "T", "R-S-T"]


def _get_user_fields_map(data_model) -> dict:
    p = getattr(data_model, "proyecto", {}) or {}
    m = p.setdefault(K.LOAD_TABLE_USER_FIELDS, {})
    if not isinstance(m, dict):
        p[K.LOAD_TABLE_USER_FIELDS] = {}
        m = p[K.LOAD_TABLE_USER_FIELDS]
    return m


def _uf_key(workspace: str, node_id: str) -> str:
    return f"{(workspace or '').upper()}:{node_id}"


def _set_header_style(table: QTableWidget):
    configure_table_autoresize(table)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(False)
    table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    # Filas un poco más compactas y consistentes con widgets (combos, editores)
    table.verticalHeader().setDefaultSectionSize(26)


def _item(txt: str) -> QTableWidgetItem:
    it = QTableWidgetItem(str(txt))
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


class LoadTablesScreen(ScreenBase):
    SECTION = Section.LOAD_TABLES
    def __init__(self, data_model, parent=None):
        super().__init__(data_model, parent=parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        title = QLabel("Cuadros de carga")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self._build_tab_ca()
        self._build_tab_cc()

        # Startup-safe: never compute/refresh tables during __init__.
        # The SectionOrchestrator will call load_from_model() / reload_from_project()
        # on project load / section changes.
        self.enter_safe_state()

    # ------------------------- lifecycle -------------------------

    def load_from_model(self):
        """Populate UI from current DataModel."""
        self.reload_from_project()

    def save_to_model(self):
        """All changes are applied live; hook kept for consistency."""
        return

    def enter_safe_state(self) -> None:
        """Put the screen in a safe, empty state.

        Important: this must be callable during app startup *before* any project
        has been loaded. No computations, no dialogs.
        """
        # Hide groups until we have model data to show.
        for w in (getattr(self, "grp_ca_es", None), getattr(self, "grp_ca_no", None), getattr(self, "grp_cc_b1", None), getattr(self, "grp_cc_b2", None)):
            try:
                if w is not None:
                    w.setVisible(False)
            except Exception:
                pass

        # Show empty hints.
        for w in (getattr(self, "lbl_ca_empty", None), getattr(self, "lbl_cc_empty", None)):
            try:
                if w is not None:
                    w.setVisible(True)
            except Exception:
                pass

    def reload_from_project(self):
        # refresca combos + tablas
        self._refresh_ca()
        self._refresh_cc()

    # ------------------------- user fields store -------------------------

    def _user_fields_map(self) -> dict:
        """Almacena campos manuales asociados a filas (por node_id)."""
        p = getattr(self.data_model, "proyecto", {}) or {}
        m = p.setdefault(K.LOAD_TABLE_USER_FIELDS, {})
        if not isinstance(m, dict):
            p[K.LOAD_TABLE_USER_FIELDS] = {}
            m = p[K.LOAD_TABLE_USER_FIELDS]
        return m

    def _get_row_fields(self, workspace: str, node_id: str) -> dict:
        m = self._user_fields_map()
        key = f"{workspace}:{node_id}"
        d = m.get(key)
        return d if isinstance(d, dict) else {}

    def _set_row_field(self, workspace: str, node_id: str, k: str, v):
        m = self._user_fields_map()
        key = f"{workspace}:{node_id}"
        d = m.get(key)
        if not isinstance(d, dict):
            d = {}
            m[key] = d
        d[k] = v
        self.data_model.mark_dirty(True)

    def _balance_auto_map(self) -> dict:
        p = getattr(self.data_model, "proyecto", {}) or {}
        m = p.setdefault(K.LOAD_TABLE_BALANCE_AUTO, {})
        if not isinstance(m, dict):
            p[K.LOAD_TABLE_BALANCE_AUTO] = {}
            m = p[K.LOAD_TABLE_BALANCE_AUTO]
        return m

    def _get_balance_auto(self, workspace: str) -> bool:
        m = self._balance_auto_map()
        v = m.get((workspace or "").upper())
        return True if v is None else bool(v)

    def _set_balance_auto(self, workspace: str, value: bool) -> None:
        m = self._balance_auto_map()
        m[(workspace or "").upper()] = bool(value)
        self.data_model.mark_dirty(True)

    # ------------------------- CA -------------------------

    def _build_tab_ca(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        self.lbl_ca_empty = QLabel("No hay datos para generar cuadros de carga C.A.\n\n- Verifica que existan nodos en capas CA_ES / CA_NOES en Arquitectura SS/AA.\n- Verifica que hayas agregado alimentadores desde 'Alimentación tableros' y los hayas conectado." )
        self.lbl_ca_empty.setWordWrap(True)
        self.lbl_ca_empty.setProperty("mutedHint", True)
        self.lbl_ca_empty.setVisible(False)
        lay.addWidget(self.lbl_ca_empty)

        # Esencial
        self.grp_ca_es = QGroupBox("Cargas C.A. Esenciales")
        gl = QVBoxLayout(self.grp_ca_es)
        sel = QHBoxLayout()
        sel.addWidget(QLabel("Tablero:"))
        self.cmb_ca_es = QComboBox()
        self.cmb_ca_es.currentIndexChanged.connect(self._refresh_ca_es_table)
        sel.addWidget(self.cmb_ca_es, 1)
        self.chk_balance_ca_es = QCheckBox("Balance automático por fases (usa VA)")
        self.chk_balance_ca_es.setChecked(True)
        self.chk_balance_ca_es.toggled.connect(lambda v: self._on_balance_toggle("CA_ES", v))
        sel.addWidget(self.chk_balance_ca_es)
        gl.addLayout(sel)

        self.tbl_ca_es = QTableWidget()
        _set_header_style(self.tbl_ca_es)
        restore_header_state(self.tbl_ca_es.horizontalHeader(), "load_tables.tbl_ca_es.header")
        gl.addWidget(self.tbl_ca_es, 1)

        # No esencial
        self.grp_ca_no = QGroupBox("Cargas C.A. No Esenciales")
        gl2 = QVBoxLayout(self.grp_ca_no)
        sel2 = QHBoxLayout()
        sel2.addWidget(QLabel("Tablero:"))
        self.cmb_ca_no = QComboBox()
        self.cmb_ca_no.currentIndexChanged.connect(self._refresh_ca_no_table)
        sel2.addWidget(self.cmb_ca_no, 1)
        self.chk_balance_ca_no = QCheckBox("Balance automático por fases (usa VA)")
        self.chk_balance_ca_no.setChecked(True)
        self.chk_balance_ca_no.toggled.connect(lambda v: self._on_balance_toggle("CA_NOES", v))
        sel2.addWidget(self.chk_balance_ca_no)
        gl2.addLayout(sel2)

        self.tbl_ca_no = QTableWidget()
        _set_header_style(self.tbl_ca_no)
        restore_header_state(self.tbl_ca_no.horizontalHeader(), "load_tables.tbl_ca_no.header")
        gl2.addWidget(self.tbl_ca_no, 1)

        lay.addWidget(self.grp_ca_es, 1)
        lay.addWidget(self.grp_ca_no, 1)

        self.tabs.addTab(w, "C.A.")

    def _refresh_ca(self):
        # combos desde topología
        self._fill_combo(self.cmb_ca_es, list_board_nodes(self.data_model, workspace="CA_ES"))
        self._fill_combo(self.cmb_ca_no, list_board_nodes(self.data_model, workspace="CA_NOES"))

        # tablas
        self._refresh_ca_es_table()
        self._refresh_ca_no_table()

    def _refresh_ca_es_table(self):
        node_id = self._combo_node_id(self.cmb_ca_es)
        if hasattr(self, "chk_balance_ca_es"):
            self.chk_balance_ca_es.blockSignals(True)
            self.chk_balance_ca_es.setChecked(self._get_balance_auto("CA_ES"))
            self.chk_balance_ca_es.blockSignals(False)
        rows = build_ac_table(self.data_model, workspace="CA_ES", board_node_id=node_id) if node_id else []
        self._render_ac_table(self.tbl_ca_es, rows)
        self.grp_ca_es.setVisible(len(rows) > 0)

    def _refresh_ca_no_table(self):
        node_id = self._combo_node_id(self.cmb_ca_no)
        if hasattr(self, "chk_balance_ca_no"):
            self.chk_balance_ca_no.blockSignals(True)
            self.chk_balance_ca_no.setChecked(self._get_balance_auto("CA_NOES"))
            self.chk_balance_ca_no.blockSignals(False)
        rows = build_ac_table(self.data_model, workspace="CA_NOES", board_node_id=node_id) if node_id else []
        self._render_ac_table(self.tbl_ca_no, rows)
        self.grp_ca_no.setVisible(len(rows) > 0)

    def _render_ac_table(self, table: QTableWidget, rows):
        headers = [
            "Descripción de las Cargas",
            "TAG",
            "Ubicación",
            "N° ITM",
            "Capacidad ITM",
            "Capacidad Diferencial",
            "Fases",
            "Potencia [W]",
            "Factor de potencia",
            "Factor de diversidad",
            "Consumo total [VA]",
            "Corriente Fase R [A]",
            "Corriente Fase S [A]",
            "Corriente Fase T [A]",
        ]
        table.clear()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(0)

        table.setProperty("_lt_workspace", "CA_ES" if table is self.tbl_ca_es else "CA_NOES")
        balance_auto = self._get_balance_auto(table.property("_lt_workspace"))

        for r in rows:
            fields = self._get_row_fields(table.property("_lt_workspace"), r.node_id)
            i = table.rowCount()
            table.insertRow(i)
            it0 = _item(r.descripcion)
            it0.setData(Qt.UserRole, r.node_id)
            table.setItem(i, 0, it0)
            table.setItem(i, 1, _item(r.tag))
            table.setItem(i, 2, _item(r.ubicacion))
            # Campos usuario
            self._set_mcb_no_widget(table, i, 3, table.property("_lt_workspace"), r.node_id, fields.get("mcb_no", r.n_itm if r.n_itm != "-" else ""))
            self._set_combo_widget(table, i, 4, table.property("_lt_workspace"), r.node_id, "mcb_type", fields.get("mcb_type", ""), MCB_OPTIONS, editable=True)
            table.setItem(i, 5, _item(r.cap_dif))
            self._set_combo_widget(table, i, 6, table.property("_lt_workspace"), r.node_id, "phase", fields.get("phase", r.fases), PHASE_OPTIONS, editable=(not balance_auto), enabled=(not balance_auto))
            table.setItem(i, 7, _item(f"{r.p_total_w:.2f}"))
            self._set_spin_widget(table, i, 8, table.property("_lt_workspace"), r.node_id, "fp", float(fields.get("fp", r.fp)), default=0.90)
            self._set_spin_widget(table, i, 9, table.property("_lt_workspace"), r.node_id, "fd", float(fields.get("fd", r.fd)), default=1.00)
            table.setItem(i, 10, _item(f"{r.consumo_va:.2f}"))
            table.setItem(i, 11, _item(f"{r.i_r:.2f}"))
            table.setItem(i, 12, _item(f"{r.i_s:.2f}"))
            table.setItem(i, 13, _item(f"{r.i_t:.2f}"))

        configure_table_autoresize(table)

    # ------------------------- CC -------------------------

    def _build_tab_cc(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        self.lbl_cc_empty = QLabel("No hay datos para generar cuadros de carga C.C.\n\n- Verifica que existan nodos en capas CC_B1 / CC_B2 en Arquitectura SS/AA.\n- Verifica que hayas agregado alimentadores desde 'Alimentación tableros' y los hayas conectado." )
        self.lbl_cc_empty.setWordWrap(True)
        self.lbl_cc_empty.setProperty("mutedHint", True)
        self.lbl_cc_empty.setVisible(False)
        lay.addWidget(self.lbl_cc_empty)

        # Barra 1
        self.grp_cc_b1 = QGroupBox("Cargas C.C. — Barra 1")
        gl1 = QVBoxLayout(self.grp_cc_b1)
        sel1 = QHBoxLayout()
        sel1.addWidget(QLabel("Tablero:"))
        self.cmb_cc_b1 = QComboBox()
        self.cmb_cc_b1.currentIndexChanged.connect(self._refresh_cc_b1_table)
        sel1.addWidget(self.cmb_cc_b1, 1)
        gl1.addLayout(sel1)

        self.tbl_cc_b1 = QTableWidget()
        _set_header_style(self.tbl_cc_b1)
        restore_header_state(self.tbl_cc_b1.horizontalHeader(), "load_tables.tbl_cc_b1.header")
        gl1.addWidget(self.tbl_cc_b1, 1)

        # Barra 2
        self.grp_cc_b2 = QGroupBox("Cargas C.C. — Barra 2")
        gl2 = QVBoxLayout(self.grp_cc_b2)
        sel2 = QHBoxLayout()
        sel2.addWidget(QLabel("Tablero:"))
        self.cmb_cc_b2 = QComboBox()
        self.cmb_cc_b2.currentIndexChanged.connect(self._refresh_cc_b2_table)
        sel2.addWidget(self.cmb_cc_b2, 1)
        gl2.addLayout(sel2)

        self.tbl_cc_b2 = QTableWidget()
        _set_header_style(self.tbl_cc_b2)
        restore_header_state(self.tbl_cc_b2.horizontalHeader(), "load_tables.tbl_cc_b2.header")
        gl2.addWidget(self.tbl_cc_b2, 1)

        lay.addWidget(self.grp_cc_b1, 1)
        lay.addWidget(self.grp_cc_b2, 1)

        self.tabs.addTab(w, "C.C.")

    def _refresh_cc(self):
        self._fill_combo(self.cmb_cc_b1, list_board_nodes(self.data_model, workspace="CC_B1"))
        self._fill_combo(self.cmb_cc_b2, list_board_nodes(self.data_model, workspace="CC_B2"))

        self._refresh_cc_b1_table()
        self._refresh_cc_b2_table()

    def _refresh_cc_b1_table(self):
        node_id = self._combo_node_id(self.cmb_cc_b1)
        rows = build_cc_table(self.data_model, workspace="CC_B1", board_node_id=node_id) if node_id else []
        self._render_cc_table(self.tbl_cc_b1, rows)
        self.grp_cc_b1.setVisible(len(rows) > 0)

    def _refresh_cc_b2_table(self):
        node_id = self._combo_node_id(self.cmb_cc_b2)
        rows = build_cc_table(self.data_model, workspace="CC_B2", board_node_id=node_id) if node_id else []
        self._render_cc_table(self.tbl_cc_b2, rows)
        self.grp_cc_b2.setVisible(len(rows) > 0)

    def _render_cc_table(self, table: QTableWidget, rows):
        headers = [
            "Barras",
            "Descripción de las Cargas",
            "TAG",
            "Ubicación",
            "N° Circuito",
            "N° Conductores",
            "Calibre",
            "Tipo",
            "N° ITM",
            "Capacidad ITM",
            "Cargas Permanentes [W]",
            "Cargas Permanentes [A]",
            "Cargas Momentáneas [W]",
            "Cargas Momentáneas [A]",
            "Observaciones",
        ]
        table.clear()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(0)

        table.setProperty("_lt_workspace", "CC_B1" if table is self.tbl_cc_b1 else "CC_B2")

        for r in rows:
            fields = self._get_row_fields(table.property("_lt_workspace"), r.node_id)
            i = table.rowCount()
            table.insertRow(i)
            table.setItem(i, 0, _item(r.barra))
            it1 = _item(r.descripcion)
            it1.setData(Qt.UserRole, r.node_id)
            table.setItem(i, 1, it1)
            table.setItem(i, 2, _item(r.tag))
            table.setItem(i, 3, _item(r.ubicacion))
            table.setItem(i, 4, _item(r.n_circuito))
            table.setItem(i, 5, _item(r.n_conductores))
            table.setItem(i, 6, _item(r.calibre))
            table.setItem(i, 7, _item(r.tipo))
            self._set_mcb_no_widget(table, i, 8, table.property("_lt_workspace"), r.node_id, fields.get("mcb_no", r.n_itm if r.n_itm != "-" else ""))
            self._set_combo_widget(table, i, 9, table.property("_lt_workspace"), r.node_id, "mcb_type", fields.get("mcb_type", ""), MCB_OPTIONS, editable=True)
            table.setItem(i, 10, _item(f"{r.p_perm_w:.2f}"))
            table.setItem(i, 11, _item(f"{r.i_perm_a:.2f}"))
            table.setItem(i, 12, _item(f"{r.p_mom_w:.2f}"))
            table.setItem(i, 13, _item(f"{r.i_mom_a:.2f}"))
            table.setItem(i, 14, _item(r.obs))

        configure_table_autoresize(table)

    # ------------------------- helpers -------------------------

    def _fill_combo(self, combo: QComboBox, items):
        """items = [(id,label), ...]"""
        combo.blockSignals(True)
        try:
            cur = self._combo_node_id(combo)
            combo.clear()
            for nid, label in items:
                combo.addItem(label, nid)
            # intentar restaurar
            if cur:
                idx = combo.findData(cur)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        finally:
            combo.blockSignals(False)

    @staticmethod
    def _combo_node_id(combo: QComboBox):
        if combo.count() <= 0:
            return ""
        return str(combo.currentData() or "")

    # ------------------------- widgets helpers (editable) -------------------------

    def _set_combo_widget(self, table: QTableWidget, row: int, col: int, workspace: str, node_id: str,
                          key: str, value: str, options, editable: bool = True, enabled: bool = True):
        cb = QComboBox()
        cb.setEditable(editable)
        cb.addItems(list(options or []))
        v = (value or "").strip()
        if v:
            if cb.findText(v) < 0:
                cb.addItem(v)
            cb.setCurrentText(v)
        cb.setEnabled(bool(enabled))
        if not enabled:
            cb.setStyleSheet(
                "QComboBox { background: transparent; }"
                "QComboBox:disabled { background: transparent; color: #000000; }"
                "QComboBox::drop-down:disabled { background: transparent; border: 0px; }"
            )
        else:
            cb.setStyleSheet("QComboBox { background: #FFF9C4; }")
        cb.currentTextChanged.connect(lambda _t: self._on_combo_changed(table, row, workspace, node_id, key, cb))
        table.setCellWidget(row, col, cb)

    def _set_mcb_no_widget(self, table: QTableWidget, row: int, col: int, workspace: str, node_id: str, value: str):
        ed = QLineEdit()
        ed.setText((value or "").strip())
        ed.setPlaceholderText("Ej: F201 / QA101")
        ed.editingFinished.connect(lambda: self._on_mcb_no_changed(table, workspace, node_id, ed))
        table.setCellWidget(row, col, ed)

    def _set_spin_widget(self, table: QTableWidget, row: int, col: int, workspace: str, node_id: str,
                         key: str, value: float, default: float = 1.0):
        sp = QDoubleSpinBox()
        sp.setDecimals(2)
        sp.setSingleStep(0.05)
        sp.setRange(0.0, 1000.0)
        try:
            sp.setValue(float(value))
        except Exception:
            sp.setValue(float(default))
        sp.valueChanged.connect(lambda v: self._on_spin_changed(workspace, node_id, key, float(v)))
        table.setCellWidget(row, col, sp)

    def _on_combo_changed(self, _table: QTableWidget, _row: int, workspace: str, node_id: str, key: str, cb: QComboBox):
        self._set_row_field(workspace, node_id, key, cb.currentText().strip())

    def _on_spin_changed(self, workspace: str, node_id: str, key: str, val: float):
        self._set_row_field(workspace, node_id, key, float(val))
        if key in ("fp", "fd"):
            if workspace == "CA_ES":
                self._refresh_ca_es_table()
            elif workspace == "CA_NOES":
                self._refresh_ca_no_table()

    def _on_mcb_no_changed(self, table: QTableWidget, workspace: str, node_id: str, ed: QLineEdit):
        txt = ed.text().strip()
        self._set_row_field(workspace, node_id, "mcb_no", txt)
        self._autofill_mcb_numbers(table)

    def _on_balance_toggle(self, workspace: str, value: bool):
        self._set_balance_auto(workspace, bool(value))
        if workspace == "CA_ES":
            self._refresh_ca_es_table()
        elif workspace == "CA_NOES":
            self._refresh_ca_no_table()

    def _autofill_mcb_numbers(self, table: QTableWidget):
        """Autocompleta correlativo hacia abajo en la misma tabla, desde el primer MCB válido."""
        # buscar primera celda con formato PREFIJO+NUM
        first = None
        for r in range(table.rowCount()):
            w = table.cellWidget(r, 3) if table is self.tbl_ca_es or table is self.tbl_ca_no else table.cellWidget(r, 8)
            if isinstance(w, QLineEdit):
                txt = (w.text() or "").strip()
                if txt:
                    m = re.match(r"^([A-Za-z_-]*)(\d+)$", txt)
                    if not m:
                        return
                    first = (r, m.group(1), int(m.group(2)), len(m.group(2)))
                    break
        if not first:
            return
        r0, prefix, num0, width = first
        n = num0
        col = 3 if (table is self.tbl_ca_es or table is self.tbl_ca_no) else 8
        workspace = str(table.property("_lt_workspace") or "")
        for r in range(r0 + 1, table.rowCount()):
            w = table.cellWidget(r, col)
            if not isinstance(w, QLineEdit):
                continue
            if (w.text() or "").strip():
                continue
            n += 1
            w.blockSignals(True)
            w.setText(f"{prefix}{n:0{width}d}")
            w.blockSignals(False)
            nid = self._row_node_id(table, r)
            if nid:
                self._set_row_field(workspace, nid, "mcb_no", f"{prefix}{n:0{width}d}")

    @staticmethod
    def _row_node_id(table: QTableWidget, row: int) -> str:
        """Busca el node_id guardado en Qt.UserRole en algún item de la fila."""
        for c in range(table.columnCount()):
            it = table.item(row, c)
            if it is None:
                continue
            v = it.data(Qt.UserRole)
            if v:
                return str(v)
        return ""



    def closeEvent(self, event):
        """Persist header state (best-effort)."""
        try:
            if hasattr(self, "tbl_ca_es") and self.tbl_ca_es is not None:
                save_header_state(self.tbl_ca_es.horizontalHeader(), "load_tables.tbl_ca_es.header")
            if hasattr(self, "tbl_ca_no") and self.tbl_ca_no is not None:
                save_header_state(self.tbl_ca_no.horizontalHeader(), "load_tables.tbl_ca_no.header")
            if hasattr(self, "tbl_cc_b1") and self.tbl_cc_b1 is not None:
                save_header_state(self.tbl_cc_b1.horizontalHeader(), "load_tables.tbl_cc_b1.header")
            if hasattr(self, "tbl_cc_b2") and self.tbl_cc_b2 is not None:
                save_header_state(self.tbl_cc_b2.horizontalHeader(), "load_tables.tbl_cc_b2.header")
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
        try:
            super().closeEvent(event)
        except Exception:
            event.accept()
