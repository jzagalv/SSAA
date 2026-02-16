# -*- coding: utf-8 -*-
"""database_screen.py

Editor de librería de **Consumos**.

La librería es un archivo `.lib` que internamente es JSON plano.

Header requerido:

{
  "file_type": "SSAA_LIB_CONSUMOS",
  "schema_version": 1,
  "name": "Consumos",
  "items": [ ... ]
}

Notas importantes:
- La librería es GLOBAL/REUTILIZABLE, pero **NO** modifica por sí sola
  los datos del proyecto ya guardados (evita cambiar proyectos antiguos).
- Este editor sólo modifica el archivo .lib seleccionado/cargado.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor
from ui.theme import get_theme_token
from ui.utils.table_utils import configure_table_autoresize, request_autofit
from ui.utils.user_signals import connect_lineedit_user_live
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.sections import Section

from ui.table_utils import make_table_sortable, center_in_cell


# índices de columnas
COL_EQUIPO = 0
COL_CODE = 1
COL_MARCA = 2
COL_MODELO = 3
COL_P_W = 4
COL_P_VA = 5
COL_USAR_VA = 6
COL_ALIMENTADOR = 7
COL_TIPO = 8
COL_FASE = 9
COL_LIB_UID = 10  # oculto (no editable)


def _normalize_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(raw or {})
    # Identidad estable del item de librería
    uid = str(d.get("lib_uid", "") or "").strip()
    try:
        uid = str(uuid.UUID(uid)) if uid else ""
    except Exception:
        uid = ""
    if not uid:
        uid = str(uuid.uuid4())
    d["lib_uid"] = uid

    d.setdefault("code", "")
    d.setdefault("name", "")
    d.setdefault("marca", "")
    d.setdefault("modelo", "")
    # compat: potencia_cc/potencia -> potencia_w
    if "potencia_w" not in d:
        if "potencia_cc" in d:
            d["potencia_w"] = d.get("potencia_cc")
        elif "potencia" in d:
            d["potencia_w"] = d.get("potencia")
        else:
            d["potencia_w"] = ""
    d.setdefault("potencia_va", "")
    d["usar_va"] = bool(d.get("usar_va", False))
    d.setdefault("alimentador", "General")
    d.setdefault("tipo_consumo", "C.C. permanente")
    d.setdefault("fase", "1F")
    return d


class ComponentDatabaseScreen(QDialog):
    """Se mantiene el nombre por compatibilidad con main.py.

    Internamente es un editor de librería de consumos (.lib).
    """

    SECTION = Section.PROJECT

    def __init__(self, data_model, parent=None):
        super().__init__(parent)
        self.data_model = data_model

        # Modal + siempre al frente (evita múltiples instancias y estados inconsistentes)
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.setWindowTitle("Librería de Consumos")
        self.resize(1120, 560)

        self._dirty = False
        self._loading = False

        self.lib_path: str = str(getattr(self.data_model, "library_paths", {}).get("consumos", "") or "")
        self.data: Dict[str, Any] = {
            "file_type": "SSAA_LIB_CONSUMOS",
            "schema_version": 1,
            "name": "Consumos",
            "items": [],
        }

        # Si ya hay una librería cargada en DataModel, la usamos.
        loaded = getattr(self.data_model, "library_data", {}).get("consumos")
        if isinstance(loaded, dict) and loaded.get("file_type") == "SSAA_LIB_CONSUMOS":
            self.data = dict(loaded)

        self._build_ui()
        self._refresh_header_info()

        self._loading = True
        self._populate_table()
        self._apply_all_rules()
        self._loading = False

        self.table.setSortingEnabled(True)
        self.table.itemChanged.connect(self._on_item_changed)

    # ----------------- UI -----------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # header (ruta + nombre)
        top = QHBoxLayout()
        layout.addLayout(top)

        # Información de librería activa (sin controles de carga aquí, para evitar redundancia
        # porque la asignación se hace en la ventana dedicada de librerías).
        self.lbl_path = QLabel("(sin librería cargada)")
        self.lbl_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_path.setToolTip("Ruta de la librería activa")
        top.addWidget(QLabel("Librería:"))
        top.addWidget(self.lbl_path, 1)
        self.btn_load = None

        top.addWidget(QLabel("Nombre:"))
        self.txt_name = QLineEdit()
        connect_lineedit_user_live(self.txt_name, lambda _t: self._on_name_changed())
        top.addWidget(self.txt_name)

        # filtros
        filters = QHBoxLayout()
        layout.addLayout(filters)

        filters.addWidget(QLabel("Buscar:"))
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Equipo, código, marca o modelo…")
        self.txt_filter.setToolTip("Filtra por Equipo/Código/Marca/Modelo")
        self.txt_filter.textChanged.connect(self._apply_filters)
        filters.addWidget(self.txt_filter, 1)

        filters.addWidget(QLabel("Tipo:"))
        self.cmb_tipo = QComboBox()
        self.cmb_tipo.currentIndexChanged.connect(self._apply_filters)
        filters.addWidget(self.cmb_tipo)

        filters.addWidget(QLabel("Alimentador:"))
        self.cmb_alim = QComboBox()
        self.cmb_alim.currentIndexChanged.connect(self._apply_filters)
        filters.addWidget(self.cmb_alim)

        filters.addWidget(QLabel("Fase:"))
        self.cmb_fase = QComboBox()
        self.cmb_fase.currentIndexChanged.connect(self._apply_filters)
        filters.addWidget(self.cmb_fase)

        self.btn_clear_filters = QPushButton("Limpiar")
        self.btn_clear_filters.clicked.connect(self._clear_filters)
        filters.addWidget(self.btn_clear_filters)

        self.lbl_count = QLabel("Mostrando 0 de 0")
        self.lbl_count.setToolTip("Cantidad de filas visibles según filtros")
        filters.addWidget(self.lbl_count)

        # tabla
        self.table = QTableWidget(0, 11, self)
        self.table.setHorizontalHeaderLabels([
            "Equipo",
            "Código",
            "Marca",
            "Modelo",
            "Potencia [W]",
            "Potencia [VA]",
            "Usar VA",
            "Alimentador",
            "Tipo Consumo",
            "Fase",
            "lib_uid",  # oculto
        ])
        configure_table_autoresize(self.table)
        make_table_sortable(self.table)
        layout.addWidget(self.table, 1)

        # ocultamos lib_uid (columna técnica)
        self.table.setColumnHidden(COL_LIB_UID, True)

        # botones
        btns = QHBoxLayout()
        layout.addLayout(btns)

        self.btn_add = QPushButton("Agregar")
        self.btn_del = QPushButton("Eliminar")
        self.btn_save = QPushButton("Guardar")
        self.btn_save_as = QPushButton("Guardar como…")
        self.btn_close = QPushButton("Cerrar")

        self.btn_add.clicked.connect(self._add_row)
        self.btn_del.clicked.connect(self._delete_selected)
        self.btn_save.clicked.connect(self._save_to_current)
        self.btn_save_as.clicked.connect(self._save_as)
        self.btn_close.clicked.connect(self.reject)

        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_del)
        btns.addStretch()
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_save_as)
        btns.addWidget(self.btn_close)

    def _refresh_header_info(self):
        self.lbl_path.setText(self.lib_path or "(sin librería cargada)")
        self.txt_name.blockSignals(True)
        self.txt_name.setText(str(self.data.get("name", "Consumos")))
        self.txt_name.blockSignals(False)

    def _on_name_changed(self, _text: str = ""):
        if self._loading:
            return
        self.data["name"] = self.txt_name.text()
        self._dirty = True

    def _on_item_changed(self, _item: QTableWidgetItem):
        if self._loading:
            return
        self._dirty = True
        self._refresh_filter_options()
        self._apply_filters()

    def can_deactivate(self, parent=None) -> bool:
        if not self._dirty:
            return True
        resp = QMessageBox.question(
            self,
            "Cambios sin guardar",
            "Tienes cambios sin guardar en la librería de consumos.\n\n"
            "¿Deseas guardar antes de continuar?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if resp == QMessageBox.Save:
            return bool(self._save_to_current(show_message=False))
        if resp == QMessageBox.Discard:
            lib_path = str(self.lib_path or "").strip()
            if lib_path and os.path.exists(lib_path):
                return bool(self._load_lib_path(lib_path))
            self._dirty = False
            return True
        return False

    def can_close(self, parent=None) -> bool:
        return self.can_deactivate(parent)

    def reject(self):
        if self.can_close(self):
            super().reject()

    def closeEvent(self, event):
        if self.can_close(self):
            event.accept()
        else:
            event.ignore()

    # ----------------- load/save -----------------
    def _pick_and_load_lib(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Cargar librería de consumos",
            "",
            "Librería (*.lib);;Todos (*.*)",
        )
        if not path:
            return
        self._load_lib_path(path)

    def _load_lib_path(self, path: str) -> bool:
        path = str(path or "").strip()
        if not path:
            return False
        try:
            data = self.data_model.load_library("consumos", path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return False

        self.lib_path = path
        self.data = dict(data)
        self._dirty = False

        self._loading = True
        self._refresh_header_info()
        self._populate_table()
        self._apply_all_rules()
        self._loading = False
        return True

    def _save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar librería de consumos como",
            "consumos.lib",
            "Librería (*.lib)",
        )
        if not path:
            return False
        if not path.lower().endswith(".lib"):
            path += ".lib"

        self.lib_path = path
        return self._save_to_path(path)

    def _save_to_current(self, show_message: bool = True) -> bool:
        if not self.lib_path:
            return self._save_as()
        return self._save_to_path(self.lib_path, show_message=show_message)

    def _save_to_path(self, path: str, show_message: bool = True) -> bool:
        self._collect_from_table()

        # asegurar header
        self.data["file_type"] = "SSAA_LIB_CONSUMOS"
        if "schema_version" not in self.data:
            self.data["schema_version"] = 1

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar la librería:\n\n{e}")
            return False

        # actualizar DataModel para que el resto de la app use la lib recién guardada
        try:
            self.data_model.load_library("consumos", path)
        except Exception:
            # ya validamos header, no debería fallar; si falla, igual no rompemos la UI
            self.data_model.set_library_path("consumos", path)
            self.data_model.library_data["consumos"] = dict(self.data)

        self._dirty = False
        self._refresh_header_info()
        if show_message:
            QMessageBox.information(self, "Guardado", "Librería de consumos guardada correctamente.")
        return True

    # ----------------- tabla -----------------
    def _populate_table(self):
        items = self.data.get("items", [])
        if not isinstance(items, list):
            items = []
        prev_loading = self._loading
        self._loading = True
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(0)
            for raw in items:
                d = _normalize_item(raw)
                self._append_row(d)
            self._refresh_filter_options()
            self._apply_filters()
            request_autofit(self.table)
        finally:
            self.table.blockSignals(False)
            self._loading = prev_loading

    def _append_row(self, d: Dict[str, Any] | None = None):
        d = _normalize_item(d or {})
        r = self.table.rowCount()
        self.table.insertRow(r)

        self.table.setItem(r, COL_EQUIPO, QTableWidgetItem(str(d.get("name", ""))))
        self.table.setItem(r, COL_CODE, QTableWidgetItem(str(d.get("code", ""))))
        self.table.setItem(r, COL_MARCA, QTableWidgetItem(str(d.get("marca", ""))))
        self.table.setItem(r, COL_MODELO, QTableWidgetItem(str(d.get("modelo", ""))))
        self.table.setItem(r, COL_P_W, QTableWidgetItem(str(d.get("potencia_w", ""))))
        self.table.setItem(r, COL_P_VA, QTableWidgetItem("" if d.get("potencia_va") in (None, "") else str(d.get("potencia_va"))))

        # lib_uid (técnico, oculto)
        it_uid = QTableWidgetItem(str(d.get("lib_uid", "")))
        it_uid.setFlags(it_uid.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(r, COL_LIB_UID, it_uid)

        chk = QCheckBox()
        chk.setChecked(bool(d.get("usar_va", False)))
        chk.stateChanged.connect(lambda _s: self._on_widget_changed())
        self.table.setCellWidget(r, COL_USAR_VA, center_in_cell(chk))

        alim = QComboBox()
        alim.addItems(["General", "Individual", "Indirecta"])
        alim.setCurrentText(str(d.get("alimentador", "General")))
        alim.currentTextChanged.connect(lambda _t: self._on_widget_changed())
        self.table.setCellWidget(r, COL_ALIMENTADOR, alim)

        tipo = QComboBox()
        tipo.addItems([
            "C.C. permanente",
            "C.C. momentáneo",
            "C.C. aleatorio",
            "C.A. Esencial",
            "C.A. No Esencial",
        ])
        tipo.setCurrentText(str(d.get("tipo_consumo", "C.C. permanente")))
        tipo.currentTextChanged.connect(lambda _t: self._on_widget_changed())
        self.table.setCellWidget(r, COL_TIPO, tipo)

        fase = QComboBox()
        fase.addItems(["1F", "3F"])
        fase.setCurrentText(str(d.get("fase", "1F")))
        fase.currentTextChanged.connect(lambda _t: self._on_widget_changed())
        self.table.setCellWidget(r, COL_FASE, fase)

    def _on_widget_changed(self):
        if self._loading:
            return
        self._dirty = True
        self._apply_all_rules()
        self._refresh_filter_options()
        self._apply_filters()

    def _add_row(self):
        self._append_row({})
        self._dirty = True
        self._apply_all_rules()
        self._refresh_filter_options()
        self._apply_filters()
        request_autofit(self.table)

    def _delete_selected(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for r in rows:
            self.table.removeRow(r)
        self._dirty = True
        self._refresh_filter_options()
        self._apply_filters()
        request_autofit(self.table)

    def _collect_from_table(self):
        items: List[Dict[str, Any]] = []
        for r in range(self.table.rowCount()):
            name = self._item_text(r, COL_EQUIPO)
            code = self._item_text(r, COL_CODE)
            marca = self._item_text(r, COL_MARCA)
            modelo = self._item_text(r, COL_MODELO)
            pw = self._item_text(r, COL_P_W)
            pva = self._item_text(r, COL_P_VA)
            usar_va = self._checkbox_at(r, COL_USAR_VA)
            alim = self._combo_at(r, COL_ALIMENTADOR)
            tipo = self._combo_at(r, COL_TIPO)
            fase = self._combo_at(r, COL_FASE)

            # lib_uid ...
            lib_uid = self._item_text(r, COL_LIB_UID)

            items.append(_normalize_item({
                "lib_uid": lib_uid,
                "code": code,
                "name": name,
                "marca": marca,
                "modelo": modelo,
                "potencia_w": pw,
                "potencia_va": pva,
                "usar_va": usar_va,
                "alimentador": alim,
                "tipo_consumo": tipo,
                "fase": fase,
            }))

        self.data["items"] = items

    def _item_text(self, row: int, col: int) -> str:
        it = self.table.item(row, col)
        return it.text().strip() if it else ""

    def _checkbox_at(self, row: int, col: int) -> bool:
        w = self.table.cellWidget(row, col)
        if isinstance(w, QCheckBox):
            return w.isChecked()
        if w is None:
            return False
        chk = w.findChild(QCheckBox)
        return bool(chk.isChecked()) if chk else False

    def _combo_at(self, row: int, col: int) -> str:
        w = self.table.cellWidget(row, col)
        return w.currentText() if isinstance(w, QComboBox) else ""

    def _collect_unique_values(self, col_index: int) -> List[str]:
        values = set()
        for r in range(self.table.rowCount()):
            if col_index in (COL_ALIMENTADOR, COL_TIPO, COL_FASE):
                text = self._combo_at(r, col_index).strip()
            else:
                text = self._item_text(r, col_index).strip()
            if text:
                values.add(text)
        return sorted(values, key=str.casefold)

    def _refresh_filter_options(self):
        if not hasattr(self, "cmb_tipo"):
            return

        def _rebuild_combo(combo: QComboBox, values: List[str]) -> None:
            prev = combo.currentText().strip()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Todos")
            for v in values:
                combo.addItem(v)
            idx = combo.findText(prev) if prev else -1
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

        _rebuild_combo(self.cmb_tipo, self._collect_unique_values(COL_TIPO))
        _rebuild_combo(self.cmb_alim, self._collect_unique_values(COL_ALIMENTADOR))
        _rebuild_combo(self.cmb_fase, self._collect_unique_values(COL_FASE))

    def _clear_filters(self, *_args):
        if not hasattr(self, "txt_filter"):
            return
        self.txt_filter.blockSignals(True)
        self.txt_filter.clear()
        self.txt_filter.blockSignals(False)
        for combo in (self.cmb_tipo, self.cmb_alim, self.cmb_fase):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self._apply_filters()

    def _apply_filters(self, *_args):
        if not hasattr(self, "table"):
            return
        q = self.txt_filter.text().strip().casefold() if hasattr(self, "txt_filter") else ""
        tipo_sel = self.cmb_tipo.currentText().strip() if hasattr(self, "cmb_tipo") else "Todos"
        alim_sel = self.cmb_alim.currentText().strip() if hasattr(self, "cmb_alim") else "Todos"
        fase_sel = self.cmb_fase.currentText().strip() if hasattr(self, "cmb_fase") else "Todos"

        shown = 0
        total = self.table.rowCount()
        for r in range(total):
            haystack = " ".join([
                self._item_text(r, COL_EQUIPO),
                self._item_text(r, COL_CODE),
                self._item_text(r, COL_MARCA),
                self._item_text(r, COL_MODELO),
            ]).casefold()
            match_text = (not q) or (q in haystack)
            match_tipo = (tipo_sel == "Todos") or (self._combo_at(r, COL_TIPO) == tipo_sel)
            match_alim = (alim_sel == "Todos") or (self._combo_at(r, COL_ALIMENTADOR) == alim_sel)
            match_fase = (fase_sel == "Todos") or (self._combo_at(r, COL_FASE) == fase_sel)

            visible = bool(match_text and match_tipo and match_alim and match_fase)
            self.table.setRowHidden(r, not visible)
            if visible:
                shown += 1

        if hasattr(self, "lbl_count"):
            self.lbl_count.setText(f"Mostrando {shown} de {total}")

    # ----------------- reglas visuales -----------------
    def _apply_all_rules(self):
        """Aplica reglas W/VA y C.C./C.A. a todas las filas."""
        disabled_brush = QBrush(QColor(get_theme_token("INPUT_DISABLED_BG", "#EBEBEB")))
        normal_brush = QBrush(QColor(get_theme_token("SURFACE", "#FFFFFF")))

        for r in range(self.table.rowCount()):
            tipo = self._combo_at(r, COL_TIPO)
            usar_va = self._checkbox_at(r, COL_USAR_VA)
            item_w = self.table.item(r, COL_P_W)
            item_va = self.table.item(r, COL_P_VA)
            if item_w is None:
                item_w = QTableWidgetItem("")
                self.table.setItem(r, COL_P_W, item_w)
            if item_va is None:
                item_va = QTableWidgetItem("")
                self.table.setItem(r, COL_P_VA, item_va)

            flags_w = item_w.flags()
            flags_va = item_va.flags()

            # Consumos C.C. => VA no aplica
            if str(tipo).startswith("C.C."):
                item_va.setText("----")
                item_va.setFlags(flags_va & ~Qt.ItemIsEditable)
                item_va.setBackground(disabled_brush)

                item_w.setFlags(flags_w | Qt.ItemIsEditable)
                item_w.setBackground(normal_brush)
                continue

            # Consumos C.A. => W o VA según checkbox
            if usar_va:
                item_va.setFlags(flags_va | Qt.ItemIsEditable)
                item_va.setBackground(normal_brush)
                item_w.setText("----")
                item_w.setFlags(flags_w & ~Qt.ItemIsEditable)
                item_w.setBackground(disabled_brush)
            else:
                item_w.setFlags(flags_w | Qt.ItemIsEditable)
                item_w.setBackground(normal_brush)
                item_va.setText("----")
                item_va.setFlags(flags_va & ~Qt.ItemIsEditable)
                item_va.setBackground(disabled_brush)
