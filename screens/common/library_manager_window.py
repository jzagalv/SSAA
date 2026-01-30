# -*- coding: utf-8 -*-
"""library_manager_window.py

Gestor de librerías (.lib) para:
- Consumos
- Materiales

Formato: JSON plano + extensión .lib

Requisitos de seguridad:
- Validar header 'file_type' para evitar que el usuario cargue el archivo equivocado.
- NO modificar el proyecto al abrir. La librería solo alimenta catálogos/propuestas.
"""

from __future__ import annotations

import json

from infra.settings import load_settings, save_settings

import os
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QCheckBox, QGroupBox, QFormLayout,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QAbstractItemView,
)


class ConsumosUpdatePreviewDialog(QDialog):
    """Vista previa tipo diff para cambios que aplicará la librería de consumos."""

    def __init__(self, parent, plan: list):
        super().__init__(parent)
        self.setWindowTitle("Previsualización de actualización")
        self.resize(980, 560)
        self._plan = plan

        root = QVBoxLayout(self)
        lbl = QLabel(
            f"Se detectaron <b>{len(plan)}</b> consumos con cambios en la librería. "
            "Revisa antes de aplicar."
        )
        root.addWidget(lbl)

        # Selector maestro (tri-state): permite marcar/desmarcar todas las filas
        # y reflejar estado mixto cuando el usuario desmarca algunas.
        self.chk_all = QCheckBox("Actualizar todo")
        self.chk_all.setTristate(True)
        self.chk_all.setCheckState(Qt.Checked)
        self.chk_all.stateChanged.connect(self._on_master_changed)
        root.addWidget(self.chk_all)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Instalación", "Gabinete", "Consumo", "Campos", "Actual → Nuevo", "Aplicar"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        # Asegura que el usuario pueda marcar/desmarcar "Aplicar" incluso si
        # el click es capturado por la tabla (tema típico en QTableWidget).
        self.table.cellClicked.connect(self._on_cell_clicked)
        root.addWidget(self.table, 1)

        self._populate()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Aplicar")
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        root.addWidget(btns)

    def _populate(self):
        self.table.setRowCount(len(self._plan))
        # Mejor legibilidad del diff: saltos de línea dentro de celdas.
        self.table.setWordWrap(True)

        def _fmt(v):
            """Formatea valores para el diff (evita 'None', recorta whitespace)."""
            if v is None:
                return "—"
            s = str(v)
            s = s.replace("\n", " ").strip()
            return s if s != "" else "—"

        for r, it in enumerate(self._plan):
            inst = str(it.get("instalacion", ""))
            gab = str(it.get("gabinete", ""))
            comp = str(it.get("consumo", ""))
            changes = it.get("changes", {}) or {}

            # Columna 'Campos': uno por línea (más legible que un CSV).
            fields = "\n".join(list(changes.keys())) if changes else "—"

            # Columna 'Actual → Nuevo': una línea por cambio.
            diff_lines = []
            for k, (a, b) in changes.items():
                diff_lines.append(f"{k}: {_fmt(a)} → {_fmt(b)}")
            diff = "\n".join(diff_lines)

            self.table.setItem(r, 0, QTableWidgetItem(inst))
            self.table.setItem(r, 1, QTableWidgetItem(gab))
            self.table.setItem(r, 2, QTableWidgetItem(comp))
            it_fields = QTableWidgetItem(fields)
            it_diff = QTableWidgetItem(diff)
            # Tooltip con el diff completo (útil cuando se recorta por ancho).
            if diff:
                it_diff.setToolTip(diff)
            self.table.setItem(r, 3, it_fields)
            self.table.setItem(r, 4, it_diff)

            chk = QCheckBox()
            chk.setChecked(True)
            # Importante: dejar siempre interactivo; el "Actualizar todo" solo
            # marca/desmarca masivamente, pero el usuario puede excluir filas.
            chk.stateChanged.connect(self._sync_master_from_rows)
            self.table.setCellWidget(r, 5, chk)

        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def _on_master_changed(self, state: int):
        """Marca/desmarca todas las filas desde el selector maestro."""
        if state == Qt.PartiallyChecked:
            return
        check = state == Qt.Checked
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, 5)
            if isinstance(w, QCheckBox):
                w.blockSignals(True)
                w.setChecked(check)
                w.blockSignals(False)
        self._sync_master_from_rows()

    def _sync_master_from_rows(self):
        """Actualiza el estado tri-state del selector maestro según filas."""
        total = self.table.rowCount()
        checked = 0
        for r in range(total):
            w = self.table.cellWidget(r, 5)
            if isinstance(w, QCheckBox) and w.isChecked():
                checked += 1

        self.chk_all.blockSignals(True)
        if checked == 0:
            self.chk_all.setCheckState(Qt.Unchecked)
        elif checked == total:
            self.chk_all.setCheckState(Qt.Checked)
        else:
            self.chk_all.setCheckState(Qt.PartiallyChecked)
        self.chk_all.blockSignals(False)

    def _on_cell_clicked(self, row: int, col: int):
        """Toggle explícito para la columna "Aplicar"."""
        if col != 5:
            return
        w = self.table.cellWidget(row, 5)
        if isinstance(w, QCheckBox) and w.isEnabled():
            w.setChecked(not w.isChecked())

    def selected_plan_ids(self) -> list:
        """Retorna índices del plan a aplicar. Si 'Actualizar todo', retorna None."""
        # Ojo: isChecked() es True también en estado parcial.
        if self.chk_all.checkState() == Qt.Checked:
            return None
        ids = []
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, 5)
            if isinstance(w, QCheckBox) and w.isChecked():
                ids.append(r)
        return ids


class LibraryManagerWindow(QDialog):
    """Ventana flotante para cargar librerías de Consumos y Materiales."""

    def __init__(self, data_model, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestor de librerías")
        self.setWindowFlags(self.windowFlags() | Qt.Tool)
        self.setModal(False)
        self.data_model = data_model

        self._orig_paths = dict(getattr(self.data_model, "library_paths", {}) or {})
        self._pending_paths = dict(self._orig_paths)
        self._pending_data = dict(getattr(self.data_model, "library_data", {}) or {})
        self._dirty = False

        self._build_ui()
        self._load_from_settings_and_model()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        info = QLabel(
            "Selecciona las librerías (.lib) que quieres usar para este entorno.\n"
            "Las librerías NO cambian los datos del proyecto automáticamente;\n"
            "solo alimentan catálogos y propuestas."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        # Consumos
        gb_cons = QGroupBox("Librería de consumos")
        form1 = QFormLayout(gb_cons)
        self.ed_cons_path = QLineEdit()
        self.ed_cons_path.setReadOnly(True)
        row1 = QHBoxLayout()
        btn1 = QPushButton("Cargar…")
        btn1.clicked.connect(lambda: self._pick_and_load("consumos"))
        btn1_clear = QPushButton("Limpiar")
        btn1_clear.clicked.connect(lambda: self._clear("consumos"))
        row1.addWidget(self.ed_cons_path, 1)
        row1.addWidget(btn1)
        row1.addWidget(btn1_clear)
        form1.addRow("Archivo:", row1)
        self.lb_cons_status = QLabel("(sin cargar)")
        form1.addRow("Estado:", self.lb_cons_status)

        # Acción explícita: actualizar proyecto desde librería
        rowu = QHBoxLayout()
        rowu.addStretch(1)
        self.btn_update_from_lib = QPushButton("Actualizar consumos del proyecto…")
        self.btn_update_from_lib.clicked.connect(self._update_project_from_consumos_lib)
        rowu.addWidget(self.btn_update_from_lib)
        form1.addRow("", rowu)
        root.addWidget(gb_cons)

        # Materiales
        gb_mat = QGroupBox("Librería de materiales")
        form2 = QFormLayout(gb_mat)
        self.ed_mat_path = QLineEdit()
        self.ed_mat_path.setReadOnly(True)
        row2 = QHBoxLayout()
        btn2 = QPushButton("Cargar…")
        btn2.clicked.connect(lambda: self._pick_and_load("materiales"))
        btn2_clear = QPushButton("Limpiar")
        btn2_clear.clicked.connect(lambda: self._clear("materiales"))
        row2.addWidget(self.ed_mat_path, 1)
        row2.addWidget(btn2)
        row2.addWidget(btn2_clear)
        form2.addRow("Archivo:", row2)
        self.lb_mat_status = QLabel("(sin cargar)")
        form2.addRow("Estado:", self.lb_mat_status)
        root.addWidget(gb_mat)

        # Opciones
        self.chk_remember = QCheckBox("Recordar estas librerías como predeterminadas")
        self.chk_remember.setChecked(True)
        root.addWidget(self.chk_remember)

        # Botones
        rowb = QHBoxLayout()
        self.btn_apply = QPushButton("Aplicar")
        self.btn_apply.clicked.connect(self._apply_changes)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self._cancel_and_close)
        rowb.addStretch(1)
        rowb.addWidget(self.btn_apply)
        rowb.addWidget(btn_cancel)
        root.addLayout(rowb)


        self.resize(720, 320)

    def _load_from_settings_and_model(self):
        # Partimos desde lo que ya está aplicado en el DataModel
        cons = self._pending_paths.get("consumos", "") or ""
        mat = self._pending_paths.get("materiales", "") or ""

        # Si no hay nada aplicado, usar settings como sugerencia (no aplica cambios automáticamente)
        s = load_settings()
        cons = cons or (s.get("consumos_lib_path") or "")
        mat = mat or (s.get("materiales_lib_path") or "")

        self._pending_paths["consumos"] = cons
        self._pending_paths["materiales"] = mat

        self.ed_cons_path.setText(cons)
        self.ed_mat_path.setText(mat)

        # No auto-cargamos para no generar efectos colaterales silenciosos.
        self._refresh_status_labels()

    def _status_text(self, kind: str) -> str:
        path = self._pending_paths.get(kind, "")
        loaded = self._pending_data.get(kind)
        if not path:
            return "(sin cargar)"
        if not os.path.exists(path):
            return "⚠️ Archivo no encontrado"
        if loaded is None:
            return "(seleccionado, no cargado)"
        name = str(loaded.get("name", "")) or "(sin nombre)"
        ver = loaded.get("schema_version", 1)
        n_items = None
        if kind == "consumos":
            items = loaded.get("items")
            if isinstance(items, list):
                n_items = len(items)
        elif kind == "materiales":
            items = loaded.get("items")
            if isinstance(items, dict):
                count = 0
                for k, v in items.items():
                    if isinstance(v, list):
                        count += len(v)
                n_items = count if count else None
            else:
                # compat (formatos antiguos)
                count = 0
                for k in ("mcb", "cables"):
                    v = loaded.get(k)
                    if isinstance(v, list):
                        count += len(v)
                n_items = count if count else None
        extra = f" | ítems: {n_items}" if n_items is not None else ""
        return f"✅ {name} (v{ver}){extra}"

    # ---------------- acciones ----------------
    def _load_and_validate(self, kind: str, path: str) -> dict:
        """Carga y valida una librería SIN aplicarla al DataModel."""
        path = self.data_model.resolve_library_path(path)
        data = self.data_model._load_json_file(path)

        expected = {"consumos": "SSAA_LIB_CONSUMOS", "materiales": "SSAA_LIB_MATERIALES"}[kind]
        file_type = (data.get("file_type") if isinstance(data, dict) else None)
        if file_type != expected:
            raise ValueError(
                f"El archivo seleccionado no corresponde a '{expected}'.\n"
                f"file_type encontrado: '{file_type or '(vacío)'}'"
            )

        schema_version = data.get("schema_version", 1)
        if not isinstance(schema_version, int) or schema_version < 1:
            raise ValueError("schema_version inválido en la librería")

        # Normalización mínima (IDs / estructura)
        if kind == "consumos":
            try:
                self.data_model._ensure_consumos_lib_uids(data)
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
        else:
            try:
                self.data_model._ensure_materiales_lib_ids(data)
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        return data

    def _mark_dirty(self):
        self._dirty = (self._pending_paths != self._orig_paths)

    def _pick_and_load(self, kind: str):
        current = self.ed_cons_path.text() if kind == "consumos" else self.ed_mat_path.text()
        start_dir = str(Path(current).parent) if current else ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar librería",
            start_dir,
            "SSAA Library (*.lib);;Todos los archivos (*.*)",
        )
        if not path:
            return
        try:
            data = self._load_and_validate(kind, path)
            self._pending_paths[kind] = self.data_model.resolve_library_path(path)
            self._pending_data[kind] = data
            self._set_line(kind, self._pending_paths[kind])
            self._mark_dirty()
            self._refresh_status_labels()
        except Exception as e:
            QMessageBox.critical(self, "Librería inválida", str(e))



    # -------------------------
    # Aplicar / Cancelar
    # -------------------------
    def _set_line(self, kind: str, value: str):
        if kind == "consumos":
            self.ed_cons_path.setText(value or "")
        elif kind == "materiales":
            self.ed_mat_path.setText(value or "")

    def _refresh_status_labels(self):
        self.lb_cons_status.setText(self._status_text("consumos"))
        self.lb_mat_status.setText(self._status_text("materiales"))

    def _clear(self, kind: str):
        self._pending_paths[kind] = ""
        self._pending_data[kind] = None
        self._set_line(kind, "")
        self._mark_dirty()
        self._refresh_status_labels()

    def _apply_changes(self):
        """Aplica los cambios (paths + data cargada) al DataModel."""
        # Aplicar paths
        for kind in ("consumos", "materiales"):
            p = (self._pending_paths.get(kind) or "").strip()
            self.data_model.set_library_path(kind, p)

            # Aplicar data (si hay path)
            if p:
                try:
                    self.data_model.library_data[kind] = self.data_model.load_library(kind, p)
                except Exception as e:
                    QMessageBox.critical(self, "Librería inválida", f"No se pudo aplicar la librería '{kind}':{e}")
                    return
            else:
                self.data_model.library_data[kind] = None

        # Recordar como predeterminadas (settings)
        if self.chk_remember.isChecked():
            s = load_settings()
            s["consumos_lib_path"] = self.data_model.library_paths.get("consumos", "")
            s["materiales_lib_path"] = self.data_model.library_paths.get("materiales", "")
            save_settings(s)

        self._dirty = False
        self.accept()

    def _cancel_and_close(self):
        """Cierra sin aplicar cambios (descarta)."""
        if self._dirty:
            r = QMessageBox.question(
                self,
                "Descartar cambios",
                "Hay cambios sin aplicar. ¿Deseas descartarlos y cerrar?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                return
        self.reject()

    def closeEvent(self, event):
        if not getattr(self, "_dirty", False):
            event.accept()
            return

        mb = QMessageBox(self)
        mb.setIcon(QMessageBox.Question)
        mb.setWindowTitle("Cambios sin aplicar")
        mb.setText("Hay cambios sin aplicar en el Gestor de librerías.")
        btn_apply = mb.addButton("Aplicar", QMessageBox.AcceptRole)
        btn_discard = mb.addButton("Descartar", QMessageBox.DestructiveRole)
        btn_cancel = mb.addButton("Cancelar", QMessageBox.RejectRole)
        mb.setDefaultButton(btn_cancel)
        mb.exec_()

        clicked = mb.clickedButton()
        if clicked == btn_apply:
            # Intentar aplicar; si falla, no cerrar
            before_dirty = self._dirty
            self._apply_changes()
            # Si _apply_changes cerró el diálogo (accept), este closeEvent puede no continuar.
            # Pero si no cerró por error, mantenemos la ventana abierta.
            if getattr(self, "_dirty", False) == before_dirty:
                event.ignore()
            else:
                event.accept()
        elif clicked == btn_discard:
            event.accept()
        else:
            event.ignore()

    def _update_project_from_consumos_lib(self):
        """Acción explícita: hoy los consumos operan como catálogo, no como datos del proyecto."""
        QMessageBox.information(
            self,
            "Actualizar consumos",
            "La librería de consumos alimenta el catálogo y propuestas."
            "Los datos del proyecto no se modifican automáticamente desde la librería.",
        )

