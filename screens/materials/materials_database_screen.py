# -*- coding: utf-8 -*-
"""materials_database_screen.py

Editor de librería de **Materiales**.

La librería es un archivo `.lib` que internamente es JSON plano.

Header requerido:

{
  "file_type": "SSAA_LIB_MATERIALES",
  "schema_version": 1,
  "name": "Materiales",
  "items": {
     "batteries": [],
     "battery_banks": [],
     "mcb": [],
     "mccb": [],
     "rccb": [],
     "rccb_mcb": []
  }
}

Notas:
- La asignación/carga de la librería activa se hace en el "Gestor de librerías".
- Este editor modifica el archivo .lib activo (o permite Guardar como...).
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

from domain.parse import to_float

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QFileDialog,
    QHeaderView,
    QFormLayout,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QDialogButtonBox,
)

from app.sections import Section


# ------------------------- helpers -------------------------

def _default_materials_lib() -> Dict[str, Any]:
    return {
        "file_type": "SSAA_LIB_MATERIALES",
        "schema_version": 1,
        "name": "Materiales",
        "items": {
            "batteries": [],
            "battery_banks": [],
            "mcb": [],
            "mccb": [],
            "rccb": [],
            "rccb_mcb": [],
        },
    }


def _ensure_items_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        data = _default_materials_lib()
    items = data.get("items")
    if not isinstance(items, dict):
        items = {}
        data["items"] = items
    for k in ("batteries", "battery_banks", "mcb", "mccb", "rccb", "rccb_mcb"):
        if not isinstance(items.get(k), list):
            items[k] = []
    return data


def _norm_battery(raw: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(raw or {})

    # UUID es el identificador primario (oculto en UI pero persistido en .lib)
    _uuid = str(d.get("uuid", "") or "").strip()
    if not _uuid:
        d["uuid"] = str(uuid.uuid4())

    # 'id' es opcional (slug legible); si no existe, se genera uno estable
    _id = str(d.get("id", "") or "").strip()
    if not _id:
        d["id"] = f"bat_{uuid.uuid4().hex[:12]}"

    d.setdefault("brand", "")
    d.setdefault("model", "")
    d.setdefault("nominal_voltage_v", "")
    d.setdefault("nominal_capacity_ah", "")
    d.setdefault("nominal_capacity_rate_h", 10)
    d.setdefault("internal_resistance_mohm", "")
    d.setdefault("float_voltage_min_v_per_cell", "")
    d.setdefault("float_voltage_max_v_per_cell", "")
    d.setdefault("constant_current_discharge", {})
    return d


# ------------------------- dialogs -------------------------

class BatteryEditDialog(QDialog):
    """Editor simple para campos principales de batería.

    (La tabla de descarga se edita en un diálogo separado para mantenerlo simple.)
    """

    def __init__(self, parent=None, data: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle("Batería")
        self.resize(560, 260)
        self.data = _norm_battery(data or {})

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        # En este editor, a propósito, usamos SOLO textbox (QLineEdit)
        # para mantener consistencia con los demás materiales.
        self.ed_brand = QLineEdit(str(self.data.get("brand", "")))
        self.ed_model = QLineEdit(str(self.data.get("model", "")))
        self.ed_vnom = QLineEdit(str(self.data.get("nominal_voltage_v", "")))
        self.ed_cap = QLineEdit(str(self.data.get("nominal_capacity_ah", "")))
        self.ed_rate = QLineEdit(str(self.data.get("nominal_capacity_rate_h", "")))
        self.ed_ri = QLineEdit(str(self.data.get("internal_resistance_mohm", "")))
        self.ed_fmin = QLineEdit(str(self.data.get("float_voltage_min_v_per_cell", "")))
        self.ed_fmax = QLineEdit(str(self.data.get("float_voltage_max_v_per_cell", "")))

        form.addRow("Marca:", self.ed_brand)
        form.addRow("Modelo:", self.ed_model)
        form.addRow("Tensión nominal [V]:", self.ed_vnom)
        form.addRow("Capacidad nominal [Ah]:", self.ed_cap)
        form.addRow("Rate nominal [h]:", self.ed_rate)
        form.addRow("Resistencia interna [mΩ]:", self.ed_ri)
        form.addRow("V flotación mín [V/celda]:", self.ed_fmin)
        form.addRow("V flotación máx [V/celda]:", self.ed_fmax)

        rowb = QHBoxLayout()
        rowb.addStretch(1)
        btn_ok = QPushButton("Aceptar")
        btn_cancel = QPushButton("Cancelar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        rowb.addWidget(btn_ok)
        rowb.addWidget(btn_cancel)
        root.addLayout(rowb)

    def get_data(self) -> Dict[str, Any]:
        d = dict(self.data)
        d["brand"] = self.ed_brand.text().strip()
        d["model"] = self.ed_model.text().strip()
        d["nominal_voltage_v"] = to_float(self.ed_vnom.text().strip(), "")
        # Guardamos como número cuando aplica, o vacío si no hay valor.
        d["nominal_capacity_ah"] = to_float(self.ed_cap.text().strip(), "")
        d["nominal_capacity_rate_h"] = to_float(self.ed_rate.text().strip(), "")
        d["internal_resistance_mohm"] = to_float(self.ed_ri.text().strip(), "")
        d["float_voltage_min_v_per_cell"] = to_float(self.ed_fmin.text().strip(), "")
        d["float_voltage_max_v_per_cell"] = to_float(self.ed_fmax.text().strip(), "")
        return d


class BatteryDischargeTableDialog(QDialog):
    """Editor de tabla de descarga de corriente constante.

    Estructura esperada:
    {
      "temperature_c": 25,
      "times_h": [...],
      "final_voltage_rows": [ {"fv_per_cell_v": 1.80, "currents_a": [...]}, ...]
    }
    """

    def __init__(self, parent=None, discharge: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle("Tabla de descarga (corriente constante)")
        self.resize(980, 420)

        self.data = dict(discharge or {})
        self.data.setdefault("temperature_c", 25)

        # tiempos por defecto (coinciden con ficha mostrada)
        default_times_h = [0.1667, 0.25, 0.5, 1, 2, 3, 5, 8, 10, 20]
        times_h = self.data.get("times_h")
        if not isinstance(times_h, list) or not times_h:
            times_h = default_times_h
            self.data["times_h"] = times_h

        # headers bonitos
        labels = ["F.V/cell"] + ["10min", "15min", "30min", "1h", "2h", "3h", "5h", "8h", "10h", "20h"]

        root = QVBoxLayout(self)
        top = QHBoxLayout()
        root.addLayout(top)
        top.addWidget(QLabel("Temp [°C]:"))
        self.sp_temp = QDoubleSpinBox()
        self.sp_temp.setRange(-50, 100)
        self.sp_temp.setDecimals(1)
        try:
            self.sp_temp.setValue(float(self.data.get("temperature_c") or 25))
        except Exception:
            self.sp_temp.setValue(25)
        top.addWidget(self.sp_temp)
        top.addStretch(1)

        self.table = QTableWidget(0, len(labels))
        self.table.setHorizontalHeaderLabels(labels)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        # botones filas
        rowb = QHBoxLayout()
        self.btn_add = QPushButton("Agregar fila FV")
        self.btn_del = QPushButton("Eliminar fila")
        self.btn_add.clicked.connect(self._add_row)
        self.btn_del.clicked.connect(self._del_row)
        rowb.addWidget(self.btn_add)
        rowb.addWidget(self.btn_del)
        rowb.addStretch(1)
        btn_ok = QPushButton("Aceptar")
        btn_cancel = QPushButton("Cancelar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        rowb.addWidget(btn_ok)
        rowb.addWidget(btn_cancel)
        root.addLayout(rowb)

        self._populate()

    def _populate(self):
        rows = self.data.get("final_voltage_rows")
        if not isinstance(rows, list):
            rows = []
            self.data["final_voltage_rows"] = rows
        self.table.setRowCount(len(rows))

        for r, it in enumerate(rows):
            fv = it.get("fv_per_cell_v", "")
            currents = it.get("currents_a", [])
            if not isinstance(currents, list):
                currents = []
            self.table.setItem(r, 0, QTableWidgetItem(str(fv)))
            for c in range(10):
                v = currents[c] if c < len(currents) else ""
                self.table.setItem(r, c + 1, QTableWidgetItem(str(v)))

        self.table.resizeRowsToContents()

    def _add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)
        # defaults
        self.table.setItem(r, 0, QTableWidgetItem("1.80"))
        for c in range(1, self.table.columnCount()):
            self.table.setItem(r, c, QTableWidgetItem(""))

    def _del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def get_data(self) -> Dict[str, Any]:
        out = {
            "temperature_c": float(self.sp_temp.value()),
            "times_h": [0.1667, 0.25, 0.5, 1, 2, 3, 5, 8, 10, 20],
            "final_voltage_rows": [],
        }
        for r in range(self.table.rowCount()):
            try:
                fv = float((self.table.item(r, 0).text() or "").strip())
            except Exception:
                continue
            currents: List[float] = []
            for c in range(1, self.table.columnCount()):
                t = (self.table.item(r, c).text() or "").strip() if self.table.item(r, c) else ""
                if t == "":
                    currents.append(0.0)
                else:
                    try:
                        currents.append(float(t.replace(",", ".")))
                    except Exception:
                        currents.append(0.0)
            out["final_voltage_rows"].append({"fv_per_cell_v": fv, "currents_a": currents})
        return out


class RCCBHelpDialog(QDialog):
    """Ventana flotante con ayuda memoria de tipos RCCB."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayuda — Tipos de RCCB")
        self.resize(760, 280)

        root = QVBoxLayout(self)

        info = QLabel(
            "Estas definiciones son una guía rápida para recordar el alcance de detección de cada tipo.\n"
            "La selección final depende del fabricante y de la aplicación."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        tbl = QTableWidget(0, 2)
        tbl.setHorizontalHeaderLabels(["Tipo", "Uso"])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(tbl, 1)

        rows = [
            ("AC", "Detectan corrientes de fuga alterna (senoidal)."),
            ("A", "Detectan corrientes de fuga alterna y pulsante (DC pulsante)."),
            ("F", "Diseñados para instalaciones con electrónica de potencia (p. ej., variadores/inversores monofásicos); detectan AC y componentes pulsantes/frecuencia mixta."),
            ("B", "Detectan AC, pulsante y DC continua (suave); típicos en variadores, UPS, cargadores EV, etc."),
            ("Asi", "Diseñados para ser menos sensibles a disparos intempestivos (mayor inmunidad a transitorios/armónicos)."),
        ]
        tbl.setRowCount(len(rows))
        for r, (t, u) in enumerate(rows):
            tbl.setItem(r, 0, QTableWidgetItem(t))
            tbl.setItem(r, 1, QTableWidgetItem(u))
        tbl.resizeRowsToContents()

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        root.addWidget(btns)


# ------------------------- main window -------------------------


class ChargerEditDialog(QDialog):
    """Editor simple de Cargadores de Batería (rectificadores/cargadores)."""

    def __init__(self, parent=None, data: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle("Cargador de batería")
        self.resize(520, 240)
        self.data = data or {}

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.ed_brand = QLineEdit(str(self.data.get("brand", "")))
        self.ed_model = QLineEdit(str(self.data.get("model", "")))

        # Solo textbox (como pediste): usamos QLineEdit y parseamos con to_float al guardar
        self.ed_vdc = QLineEdit(str(self.data.get("dc_voltage_v_1", "")))
        self.ed_iout = QLineEdit(str(self.data.get("output_current_a", "")))

        self.cb_phases = QComboBox()
        self.cb_phases.addItems(["Monofásico", "Trifásico"])
        ph = str(self.data.get("phases", "")).strip().lower()
        if "tri" in ph:
            self.cb_phases.setCurrentIndex(1)
        else:
            self.cb_phases.setCurrentIndex(0)

        form.addRow("Marca", self.ed_brand)
        form.addRow("Modelo", self.ed_model)
        form.addRow("Tensión de Salida [Vdc]", self.ed_vdc)
        form.addRow("Fases", self.cb_phases)
        form.addRow("Iout [A]", self.ed_iout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def get_data(self) -> Dict[str, Any]:
        brand = self.ed_brand.text().strip()
        model = self.ed_model.text().strip()
        vdc = to_float(self.ed_vdc.text().strip(), default=0.0)
        iout = to_float(self.ed_iout.text().strip(), default=0.0)
        phases = "monofasico" if self.cb_phases.currentIndex() == 0 else "trifasico"

        out = dict(self.data)
        out["brand"] = brand
        out["model"] = model
        out["dc_voltage_v_1"] = vdc
        out["phases"] = phases
        out["output_current_a"] = iout
        return out


class MaterialsDatabaseScreen(QDialog):
    """Editor de librería de materiales (.lib)."""

    # Considered part of project data lifecycle (libraries are project-linked).
    SECTION = Section.PROJECT

    def __init__(self, data_model, parent=None):
        super().__init__(parent)
        self.data_model = data_model
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setWindowTitle("Librería de Materiales")
        self.resize(1180, 640)

        self._dirty = False
        self._loading = False

        self.lib_path: str = str(getattr(self.data_model, "library_paths", {}).get("materiales", "") or "")
        self.data: Dict[str, Any] = _default_materials_lib()

        loaded = getattr(self.data_model, "library_data", {}).get("materiales")
        if isinstance(loaded, dict) and loaded.get("file_type") == "SSAA_LIB_MATERIALES":
            self.data = _ensure_items_dict(dict(loaded))

        self._build_ui()
        self._refresh_header()
        self._populate_batteries()
        self._populate_chargers()

    def showEvent(self, event):
        """Si el usuario cargó/cambió la librería desde el Gestor, recargar al mostrarse."""
        try:
            super().showEvent(event)
        except Exception:
            # Por seguridad, no bloquear UI
            pass

        current_path = str(getattr(self.data_model, "library_paths", {}).get("materiales", "") or "")
        if not current_path:
            return
        if current_path == getattr(self, "lib_path", ""):
            return

        # Actualizar ruta + recargar datos desde DataModel si están disponibles
        self.lib_path = current_path
        loaded = getattr(self.data_model, "library_data", {}).get("materiales")
        if not (isinstance(loaded, dict) and loaded.get("file_type") == "SSAA_LIB_MATERIALES"):
            # Intentar cargar (ya validado en Gestor); si falla, mantener datos actuales
            try:
                loaded = self.data_model.load_library("materiales", current_path)
            except Exception:
                loaded = None
        if isinstance(loaded, dict) and loaded.get("file_type") == "SSAA_LIB_MATERIALES":
            self.data = _ensure_items_dict(dict(loaded))
            self._refresh_header()
            self._populate_batteries()
            self._populate_chargers()
            self._populate_categories()


    def _build_ui(self):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        root.addLayout(top)
        top.addWidget(QLabel("Librería:"))
        self.lbl_path = QLabel("(sin librería cargada)")
        self.lbl_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        top.addWidget(self.lbl_path, 1)
        top.addWidget(QLabel("Nombre:"))
        self.ed_name = QLineEdit()
        self.ed_name.textChanged.connect(self._on_name)
        top.addWidget(self.ed_name)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # --- Batteries tab ---
        self.tab_bat = QWidget()
        vb = QVBoxLayout(self.tab_bat)

        self.tbl_bat = QTableWidget(0, 8)
        self.tbl_bat.setHorizontalHeaderLabels([
            "Marca", "Modelo", "Tensión Nominal [V]", "Ah", "Rate [h]", "Ri [mΩ]", "Float min", "Float max", "uuid"
        ])
        self.tbl_bat.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_bat.horizontalHeader().setStretchLastSection(True)
        self.tbl_bat.setColumnHidden(7, True)
        self.tbl_bat.setSelectionBehavior(self.tbl_bat.SelectRows)
        # Misma operación que otras categorías: no edición en celda, editar vía diálogo.
        self.tbl_bat.setEditTriggers(self.tbl_bat.NoEditTriggers)
        self.tbl_bat.cellDoubleClicked.connect(lambda *_: self._edit_battery())
        vb.addWidget(self.tbl_bat, 1)

        rowb = QHBoxLayout()
        self.btn_add_bat = QPushButton("Agregar")
        self.btn_del_bat = QPushButton("Eliminar")
        self.btn_edit_bat = QPushButton("Editar…")
        self.btn_discharge = QPushButton("Tabla descarga…")
        self.btn_add_bat.clicked.connect(self._add_battery)
        self.btn_del_bat.clicked.connect(self._del_battery)
        self.btn_edit_bat.clicked.connect(self._edit_battery)
        self.btn_discharge.clicked.connect(self._edit_discharge)
        rowb.addWidget(self.btn_add_bat)
        rowb.addWidget(self.btn_edit_bat)
        rowb.addWidget(self.btn_discharge)
        rowb.addWidget(self.btn_del_bat)
        rowb.addStretch(1)
        vb.addLayout(rowb)
        self.tabs.addTab(self.tab_bat, "Baterías")

        # --- Battery chargers tab (Cargadores de Batería) ---
        self.tab_chg = QWidget()
        vc = QVBoxLayout(self.tab_chg)

        self.tbl_chg = QTableWidget(0, 6)
        self.tbl_chg.setHorizontalHeaderLabels([
            "Marca", "Modelo", "Tensión de Salida [Vdc]", "Fases", "Iout [A]", "uuid"
        ])
        self.tbl_chg.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_chg.horizontalHeader().setStretchLastSection(True)
        self.tbl_chg.setColumnHidden(5, True)
        self.tbl_chg.setSelectionBehavior(self.tbl_chg.SelectRows)
        self.tbl_chg.setEditTriggers(self.tbl_chg.NoEditTriggers)
        self.tbl_chg.cellDoubleClicked.connect(lambda *_: self._edit_charger())
        vc.addWidget(self.tbl_chg, 1)

        rowc = QHBoxLayout()
        self.btn_add_chg = QPushButton("Agregar")
        self.btn_edit_chg = QPushButton("Editar...")
        self.btn_del_chg = QPushButton("Eliminar")
        self.btn_add_chg.clicked.connect(self._add_charger)
        self.btn_edit_chg.clicked.connect(self._edit_charger)
        self.btn_del_chg.clicked.connect(self._del_charger)
        rowc.addWidget(self.btn_add_chg)
        rowc.addWidget(self.btn_edit_chg)
        rowc.addWidget(self.btn_del_chg)
        rowc.addStretch(1)
        vc.addLayout(rowc)
        self.tabs.addTab(self.tab_chg, "Cargadores de Batería")

        # --- MCB tab ---
        self.tab_mcb = QWidget()
        vm = QVBoxLayout(self.tab_mcb)
        self.tbl_mcb = QTableWidget(0, 9)
        self.tbl_mcb.setHorizontalHeaderLabels([
            "N° de Polos", "Polo Neutro", "Capacidad [A]", "Curva",
            "Capacidad Cortocircuito [kA]", "Marca", "Modelo", "Código Fabricante", "uuid"
        ])
        self.tbl_mcb.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_mcb.horizontalHeader().setStretchLastSection(True)
        self.tbl_mcb.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_mcb.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_mcb.hideColumn(8)
        self.tbl_mcb.cellDoubleClicked.connect(lambda r, c: self._edit_category("mcb"))
        vm.addWidget(self.tbl_mcb, 1)
        rowm = QHBoxLayout()
        self.btn_add_mcb = QPushButton("Agregar…")
        self.btn_edit_mcb = QPushButton("Editar…")
        self.btn_del_mcb = QPushButton("Eliminar")
        self.btn_add_mcb.clicked.connect(lambda: self._add_category("mcb"))
        self.btn_edit_mcb.clicked.connect(lambda: self._edit_category("mcb"))
        self.btn_del_mcb.clicked.connect(lambda: self._del_category("mcb"))
        rowm.addWidget(self.btn_add_mcb)
        rowm.addWidget(self.btn_edit_mcb)
        rowm.addWidget(self.btn_del_mcb)
        rowm.addStretch(1)
        vm.addLayout(rowm)
        self.tabs.addTab(self.tab_mcb, "MCB")

        # --- MCCB tab ---
        self.tab_mccb = QWidget()
        v2 = QVBoxLayout(self.tab_mccb)
        self.tbl_mccb = QTableWidget(0, 11)
        self.tbl_mccb.setHorizontalHeaderLabels([
            "N° de Polos", "Polo Neutro", "Capacidad [A] (Ampere Frame)",
            "Unidad de Ajuste", "Ajuste Mínimo %", "Pasos %",
            "Capacidad Cortocircuito [kA]", "Marca", "Modelo", "Código Fabricante", "uuid"
        ])
        self.tbl_mccb.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_mccb.horizontalHeader().setStretchLastSection(True)
        self.tbl_mccb.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_mccb.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_mccb.hideColumn(10)
        self.tbl_mccb.cellDoubleClicked.connect(lambda r, c: self._edit_category("mccb"))
        v2.addWidget(self.tbl_mccb, 1)
        row2 = QHBoxLayout()
        self.btn_add_mccb = QPushButton("Agregar…")
        self.btn_edit_mccb = QPushButton("Editar…")
        self.btn_del_mccb = QPushButton("Eliminar")
        self.btn_add_mccb.clicked.connect(lambda: self._add_category("mccb"))
        self.btn_edit_mccb.clicked.connect(lambda: self._edit_category("mccb"))
        self.btn_del_mccb.clicked.connect(lambda: self._del_category("mccb"))
        row2.addWidget(self.btn_add_mccb)
        row2.addWidget(self.btn_edit_mccb)
        row2.addWidget(self.btn_del_mccb)
        row2.addStretch(1)
        v2.addLayout(row2)
        self.tabs.addTab(self.tab_mccb, "MCCB")

        # --- RCCB tab ---
        self.tab_rccb = QWidget()
        v3 = QVBoxLayout(self.tab_rccb)
        self.tbl_rccb = QTableWidget(0, 9)
        self.tbl_rccb.setHorizontalHeaderLabels([
            "N° de Polos", "Capacidad [A]", "Corriente Residual [mA]",
            "Capacidad Cortocircuito [kA]", "Tipo base",
            "Marca", "Modelo", "Código Fabricante", "uuid"
        ])
        self.tbl_rccb.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_rccb.horizontalHeader().setStretchLastSection(True)
        self.tbl_rccb.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_rccb.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_rccb.hideColumn(8)
        self.tbl_rccb.cellDoubleClicked.connect(lambda r, c: self._edit_category("rccb"))
        v3.addWidget(self.tbl_rccb, 1)
        row3 = QHBoxLayout()
        self.btn_add_rccb = QPushButton("Agregar…")
        self.btn_edit_rccb = QPushButton("Editar…")
        self.btn_del_rccb = QPushButton("Eliminar")
        self.btn_help_rccb = QPushButton("Ayuda")
        self.btn_add_rccb.clicked.connect(lambda: self._add_category("rccb"))
        self.btn_edit_rccb.clicked.connect(lambda: self._edit_category("rccb"))
        self.btn_del_rccb.clicked.connect(lambda: self._del_category("rccb"))
        self.btn_help_rccb.clicked.connect(self._show_rccb_help)
        row3.addWidget(self.btn_add_rccb)
        row3.addWidget(self.btn_edit_rccb)
        row3.addWidget(self.btn_del_rccb)
        row3.addWidget(self.btn_help_rccb)
        row3.addStretch(1)
        v3.addLayout(row3)
        self.tabs.addTab(self.tab_rccb, "RCCB")

        # --- RCCB+MCB tab ---
        self.tab_rccb_mcb = QWidget()
        v4 = QVBoxLayout(self.tab_rccb_mcb)
        self.tbl_rccb_mcb = QTableWidget(0, 11)
        self.tbl_rccb_mcb.setHorizontalHeaderLabels([
            "N° de Polos", "Polo Neutro", "Capacidad [A]", "Curva",
            "Corriente Residual [mA]", "Tipo",
            "Capacidad Cortocircuito [kA]", "Marca", "Modelo", "Referencia Fabricante", "uuid"
        ])
        self.tbl_rccb_mcb.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_rccb_mcb.horizontalHeader().setStretchLastSection(True)
        self.tbl_rccb_mcb.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_rccb_mcb.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_rccb_mcb.hideColumn(10)
        self.tbl_rccb_mcb.cellDoubleClicked.connect(lambda r, c: self._edit_category("rccb_mcb"))
        v4.addWidget(self.tbl_rccb_mcb, 1)
        row4 = QHBoxLayout()
        self.btn_add_rccb_mcb = QPushButton("Agregar…")
        self.btn_edit_rccb_mcb = QPushButton("Editar…")
        self.btn_del_rccb_mcb = QPushButton("Eliminar")
        self.btn_add_rccb_mcb.clicked.connect(lambda: self._add_category("rccb_mcb"))
        self.btn_edit_rccb_mcb.clicked.connect(lambda: self._edit_category("rccb_mcb"))
        self.btn_del_rccb_mcb.clicked.connect(lambda: self._del_category("rccb_mcb"))
        row4.addWidget(self.btn_add_rccb_mcb)
        row4.addWidget(self.btn_edit_rccb_mcb)
        row4.addWidget(self.btn_del_rccb_mcb)
        row4.addStretch(1)
        v4.addLayout(row4)
        self.tabs.addTab(self.tab_rccb_mcb, "RCCB+MCB")



        # footer buttons
        foot = QHBoxLayout()
        root.addLayout(foot)
        self.btn_save = QPushButton("Guardar")
        self.btn_save_as = QPushButton("Guardar como…")
        self.btn_close = QPushButton("Cerrar")
        self.btn_save.clicked.connect(self._save)
        self.btn_save_as.clicked.connect(self._save_as)
        self.btn_close.clicked.connect(self.close)
        foot.addWidget(self.btn_save)
        foot.addWidget(self.btn_save_as)
        foot.addStretch(1)
        foot.addWidget(self.btn_close)

    def _refresh_header(self):
        self.lbl_path.setText(self.lib_path or "(sin librería seleccionada — usa Gestor de librerías)")
        self.ed_name.setText(str(self.data.get("name", "Materiales")))

    def _on_name(self):
        self.data["name"] = self.ed_name.text().strip()
        self._dirty = True

    def _batteries(self) -> List[Dict[str, Any]]:
        self.data = _ensure_items_dict(self.data)
        return self.data["items"].get("batteries", [])


    def _chargers(self) -> List[Dict[str, Any]]:
        self.data = _ensure_items_dict(self.data)
        return self.data["items"].get("battery_banks", [])

    def _norm_charger(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(raw or {})
        _uuid = str(d.get("uuid", "") or "").strip()
        if not _uuid:
            d["uuid"] = str(uuid.uuid4())
        d.setdefault("brand", "")
        d.setdefault("model", "")
        d.setdefault("nominal_voltage_v", "")
        d.setdefault("dc_voltage_v_1", "")
        d.setdefault("phases", "")
        d.setdefault("output_current_a", "")
        return d

    
    # -------------------------
    # Generic categories (MCB/MCCB/RCCB/RCCB+MCB)
    # -------------------------
    def _category_specs(self) -> Dict[str, Dict[str, Any]]:
        return {
            "mcb": {
                "title": "MCB",
                "table": self.tbl_mcb,
                "keys": ["poles", "neutral_pole", "current_a", "curve", "short_circuit_ka", "brand", "model", "manufacturer_code", "uuid"],
                "labels": ["N° de Polos", "Polo Neutro", "Capacidad [A]", "Curva", "Capacidad Cortocircuito [kA]", "Marca", "Modelo", "Código Fabricante"],
            },
            "mccb": {
                "title": "MCCB",
                "table": self.tbl_mccb,
                "keys": ["poles", "neutral_pole", "ampere_frame_a", "trip_unit", "adj_min_pct", "steps_pct", "short_circuit_ka", "brand", "model", "manufacturer_code", "uuid"],
                "labels": ["N° de Polos", "Polo Neutro", "Capacidad [A] (Ampere Frame)", "Unidad de Ajuste", "Ajuste Mínimo %", "Pasos %", "Capacidad Cortocircuito [kA]", "Marca", "Modelo", "Código Fabricante"],
            },
            "rccb": {
                "title": "RCCB",
                "table": self.tbl_rccb,
                # Nota: UI no muestra "Tipo" ni "Uso" (ayuda memoria se muestra en botón Ayuda)
                "keys": ["poles", "current_a", "residual_ma", "short_circuit_ka", "type_base", "brand", "model", "manufacturer_code", "uuid"],
                "labels": ["N° de Polos", "Capacidad [A]", "Corriente Residual [mA]", "Capacidad Cortocircuito [kA]", "Tipo base", "Marca", "Modelo", "Código Fabricante"],
            },
            "rccb_mcb": {
                "title": "RCCB+MCB",
                "table": self.tbl_rccb_mcb,
                "keys": ["poles", "neutral_pole", "current_a", "curve", "residual_ma", "type", "short_circuit_ka", "brand", "model", "reference", "uuid"],
                "labels": ["N° de Polos", "Polo Neutro", "Capacidad [A]", "Curva", "Corriente Residual [mA]", "Tipo", "Capacidad Cortocircuito [kA]", "Marca", "Modelo", "Referencia Fabricante"],
            },
        }

    def _populate_categories(self):
        for cat in ("mcb", "mccb", "rccb", "rccb_mcb"):
            self._populate_category(cat)

    def _populate_category(self, category: str):
        specs = self._category_specs().get(category)
        if not specs:
            return
        tbl: QTableWidget = specs["table"]
        keys = specs["keys"]
        items = _ensure_items_dict(self.data).get("items", {}).get(category, []) or []
        tbl.setRowCount(0)
        for it in items:
            it = dict(it or {})
            if not str(it.get("uuid", "") or "").strip():
                it["uuid"] = str(uuid.uuid4())
            r = tbl.rowCount()
            tbl.insertRow(r)
            for c, k in enumerate(keys):
                v = it.get(k, "")
                if v is None:
                    v = ""
                item = QTableWidgetItem(str(v))
                tbl.setItem(r, c, item)
        tbl.resizeColumnsToContents()

    def _category_dialog(self, title: str, labels: List[str], initial: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(560, 240)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        lay.addLayout(form)

        edits: Dict[str, QLineEdit] = {}
        for lbl in labels:
            ed = QLineEdit()
            ed.setText(str((initial or {}).get(lbl, "") or ""))
            form.addRow(lbl + ":", ed)
            edits[lbl] = ed

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)

        if dlg.exec_() != QDialog.Accepted:
            return None

        out: Dict[str, Any] = {}
        for lbl, ed in edits.items():
            out[lbl] = ed.text().strip()
        return out

    def _add_category(self, category: str):
        specs = self._category_specs().get(category)
        if not specs:
            return
        labels = specs["labels"]
        payload = self._category_dialog(f"Agregar {specs['title']}", labels, initial=None)
        if payload is None:
            return

        rec = {"uuid": str(uuid.uuid4())}

        # map payload labels -> keys (same order)
        keys = specs["keys"]
        for k, lbl in zip(keys, labels):
            rec[k] = payload.get(lbl, "")

        _ensure_items_dict(self.data)["items"].setdefault(category, []).append(rec)
        self._set_dirty(True)
        self._populate_category(category)

    def _get_selected_uuid(self, tbl: QTableWidget, uuid_col: int) -> Optional[str]:
        r = tbl.currentRow()
        if r < 0:
            return None
        it = tbl.item(r, uuid_col)
        return str(it.text() if it else "").strip() or None

    def _edit_category(self, category: str):
        specs = self._category_specs().get(category)
        if not specs:
            return
        tbl: QTableWidget = specs["table"]
        uuid_col = len(specs["keys"]) - 1
        sel_uuid = self._get_selected_uuid(tbl, uuid_col)
        if not sel_uuid:
            QMessageBox.information(self, "Editar", "Selecciona una fila para editar.")
            return

        items = _ensure_items_dict(self.data)["items"].get(category, [])
        idx = next((i for i, x in enumerate(items) if str((x or {}).get("uuid", "")).strip() == sel_uuid), None)
        if idx is None:
            QMessageBox.warning(self, "Editar", "No se encontró el elemento seleccionado en la librería.")
            return

        current = dict(items[idx] or {})
        labels = specs["labels"]
        # build initial dict with label keys
        initial = {}
        for k, lbl in zip(specs["keys"], labels):
            initial[lbl] = current.get(k, "")

        payload = self._category_dialog(f"Editar {specs['title']}", labels, initial=initial)
        if payload is None:
            return

        for k, lbl in zip(specs["keys"], labels):
            current[k] = payload.get(lbl, "")
        current["uuid"] = sel_uuid
        items[idx] = current
        self._set_dirty(True)
        self._populate_category(category)

    def _del_category(self, category: str):
        specs = self._category_specs().get(category)
        if not specs:
            return
        tbl: QTableWidget = specs["table"]
        uuid_col = len(specs["keys"]) - 1
        sel_uuid = self._get_selected_uuid(tbl, uuid_col)
        if not sel_uuid:
            QMessageBox.information(self, "Eliminar", "Selecciona una fila para eliminar.")
            return

        if QMessageBox.question(self, "Eliminar", "¿Eliminar el elemento seleccionado?") != QMessageBox.Yes:
            return

        items = _ensure_items_dict(self.data)["items"].get(category, [])
        items = [x for x in items if str((x or {}).get("uuid", "")).strip() != sel_uuid]
        _ensure_items_dict(self.data)["items"][category] = items
        self._set_dirty(True)
        self._populate_category(category)


    def _show_rccb_help(self):
        """Abre ventana flotante con ayuda memoria de tipos RCCB."""
        dlg = RCCBHelpDialog(self)
        dlg.exec_()


    def _populate_chargers(self):
        self._loading = True
        chgs = self._chargers()
        self.tbl_chg.setRowCount(len(chgs))
        for r, c in enumerate(chgs):
            c = self._norm_charger(c)
            self.tbl_chg.setItem(r, 0, QTableWidgetItem(str(c.get("brand", ""))))
            self.tbl_chg.setItem(r, 1, QTableWidgetItem(str(c.get("model", ""))))
            self.tbl_chg.setItem(r, 2, QTableWidgetItem(str(c.get("dc_voltage_v_1", ""))))
            ph = str(c.get("phases", "")).strip().lower()
            ph_disp = "Trifásico" if "tri" in ph else ("Monofásico" if ph else "")
            self.tbl_chg.setItem(r, 3, QTableWidgetItem(ph_disp))
            self.tbl_chg.setItem(r, 4, QTableWidgetItem(str(c.get("output_current_a", ""))))
            self.tbl_chg.setItem(r, 5, QTableWidgetItem(str(c.get("uuid", ""))))
        self.tbl_chg.resizeColumnsToContents()
        self.tbl_chg.resizeRowsToContents()
        self._loading = False

    def _selected_chg_index(self) -> int:
        return self.tbl_chg.currentRow()

    def _add_charger(self):
        chg = {}
        dlg = ChargerEditDialog(self, data=chg)
        if dlg.exec_() != QDialog.Accepted:
            return
        new = dlg.get_data()
        if not new.get("uuid"):
            new["uuid"] = str(uuid.uuid4())
        # Completar campos opcionales
        new.setdefault("category", "battery_charger")
        self._chargers().append(new)
        self._dirty = True
        self._populate_chargers()



    def _edit_charger(self):
        idx = self._selected_chg_index()
        chgs = self._chargers()
        if idx < 0 or idx >= len(chgs):
            return
        dlg = ChargerEditDialog(self, data=chgs[idx])
        if dlg.exec_() != QDialog.Accepted:
            return
        new = dlg.get_data()
        # mantener uuid y vdc2 si existiera
        new.setdefault("uuid", chgs[idx].get("uuid", str(uuid.uuid4())))
        if "dc_voltage_v_2" in chgs[idx] and "dc_voltage_v_2" not in new:
            new["dc_voltage_v_2"] = chgs[idx].get("dc_voltage_v_2")
        if "family" in chgs[idx] and "family" not in new:
            new["family"] = chgs[idx].get("family")
        if "source" in chgs[idx] and "source" not in new:
            new["source"] = chgs[idx].get("source")
        if "id" in chgs[idx] and "id" not in new:
            new["id"] = chgs[idx].get("id")
        if "category" in chgs[idx] and "category" not in new:
            new["category"] = chgs[idx].get("category")
        chgs[idx] = new
        self._dirty = True
        self._populate_chargers()


    def _del_charger(self):
        idx = self._selected_chg_index()
        if idx < 0:
            return
        if QMessageBox.question(self, "Eliminar", "¿Eliminar el cargador seleccionado?") != QMessageBox.Yes:
            return
        chgs = self._chargers()
        if 0 <= idx < len(chgs):
            chgs.pop(idx)
            self._dirty = True
            self._populate_chargers()
    def _populate_batteries(self):
        self._loading = True
        bats = self._batteries()
        self.tbl_bat.setRowCount(len(bats))
        for r, b in enumerate(bats):
            b = _norm_battery(b)
            self.tbl_bat.setItem(r, 0, QTableWidgetItem(str(b.get("brand", ""))))
            self.tbl_bat.setItem(r, 1, QTableWidgetItem(str(b.get("model", ""))))
            self.tbl_bat.setItem(r, 2, QTableWidgetItem(str(b.get("nominal_voltage_v", ""))))
            self.tbl_bat.setItem(r, 3, QTableWidgetItem(str(b.get("nominal_capacity_ah", ""))))
            self.tbl_bat.setItem(r, 4, QTableWidgetItem(str(b.get("nominal_capacity_rate_h", ""))))
            self.tbl_bat.setItem(r, 5, QTableWidgetItem(str(b.get("internal_resistance_mohm", ""))))
            self.tbl_bat.setItem(r, 6, QTableWidgetItem(str(b.get("float_voltage_min_v_per_cell", ""))))
            self.tbl_bat.setItem(r, 7, QTableWidgetItem(str(b.get("float_voltage_max_v_per_cell", ""))))
            self.tbl_bat.setItem(r, 8, QTableWidgetItem(str(b.get("uuid", ""))))
        self.tbl_bat.resizeColumnsToContents()
        self.tbl_bat.resizeRowsToContents()
        self._loading = False

    def _selected_bat_index(self) -> int:
        r = self.tbl_bat.currentRow()
        return r

    def _add_battery(self):
        dlg = BatteryEditDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        b = dlg.get_data()
        bats = self._batteries()
        bats.append(b)
        self._dirty = True
        self._populate_batteries()

    def _del_battery(self):
        idx = self._selected_bat_index()
        if idx < 0:
            return
        if QMessageBox.question(self, "Eliminar", "¿Eliminar la batería seleccionada?") != QMessageBox.Yes:
            return
        bats = self._batteries()
        if 0 <= idx < len(bats):
            bats.pop(idx)
            self._dirty = True
            self._populate_batteries()

    def _edit_battery(self):
        idx = self._selected_bat_index()
        bats = self._batteries()
        if idx < 0 or idx >= len(bats):
            return
        dlg = BatteryEditDialog(self, data=bats[idx])
        if dlg.exec_() != QDialog.Accepted:
            return
        new = dlg.get_data()
        # conservar discharge si el diálogo no lo toca
        new.setdefault("constant_current_discharge", bats[idx].get("constant_current_discharge", {}))
        new["id"] = bats[idx].get("id") or new.get("id")
        bats[idx] = new
        self._dirty = True
        self._populate_batteries()

    def _edit_discharge(self):
        idx = self._selected_bat_index()
        bats = self._batteries()
        if idx < 0 or idx >= len(bats):
            return
        b = _norm_battery(bats[idx])
        dlg = BatteryDischargeTableDialog(self, discharge=b.get("constant_current_discharge") or {})
        if dlg.exec_() != QDialog.Accepted:
            return
        b["constant_current_discharge"] = dlg.get_data()
        bats[idx] = b
        self._dirty = True

    # ----------------- save -----------------
    def _save(self):
        if not self.lib_path:
            return self._save_as()
        return self._save_to(self.lib_path)

    def _save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar librería de materiales",
            self.lib_path or "materiales.lib",
            "SSAA Library (*.lib);;Todos los archivos (*.*)",
        )
        if not path:
            return
        if not path.lower().endswith(".lib"):
            path += ".lib"
        self.lib_path = path
        self._refresh_header()
        return self._save_to(path)

    def _save_to(self, path: str):
        try:
            data = _ensure_items_dict(self.data)
            data["file_type"] = "SSAA_LIB_MATERIALES"
            data["schema_version"] = 1
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # refrescar DataModel
            self.data_model.library_paths["materiales"] = path
            self.data_model.library_data["materiales"] = data
            self._dirty = False
            QMessageBox.information(self, "Guardar", "Librería de materiales guardada.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar la librería:\n\n{e}")
