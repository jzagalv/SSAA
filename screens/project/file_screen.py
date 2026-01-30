# -*- coding: utf-8 -*-
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog
)
from PyQt5.QtCore import pyqtSignal

from ui.common import dialogs
from ui.common.error_handler import run_guarded
from screens.base import ScreenBase
from data_model import _norm_project_path, PROJECT_EXT
from app.sections import Section

class FileScreen(ScreenBase):
    SECTION = Section.PROJECT
    data_loaded = pyqtSignal()

    def __init__(self, data_model, parent=None):
        super().__init__(data_model, parent)
        self.dm = self.data_model
        self._build()

    # --- ScreenBase hooks (no functional change) ---
    def load_from_model(self):
        self._refresh_fields()

    def save_to_model(self):
        return

    def _build(self):
        root = QVBoxLayout(self)

        # fila carpeta
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Carpeta del proyecto:"))
        self.ed_folder = QLineEdit()
        btn_folder = QPushButton("Elegir carpeta…")
        btn_folder.clicked.connect(self._choose_folder)
        row1.addWidget(self.ed_folder, 1)
        row1.addWidget(btn_folder)
        root.addLayout(row1)

        # fila archivo (sin .json)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Nombre de archivo (.json):"))
        self.ed_filename = QLineEdit()
        btn_name = QPushButton("Nuevo / Cambiar nombre…")
        btn_name.clicked.connect(self._choose_filename)
        row2.addWidget(self.ed_filename, 1)
        row2.addWidget(btn_name)
        root.addLayout(row2)

        # ruta resultante (sólo lectura)
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Ruta resultante:"))
        self.ed_path = QLineEdit()
        self.ed_path.setReadOnly(True)
        row3.addWidget(self.ed_path, 1)
        root.addLayout(row3)

        # botones
        row4 = QHBoxLayout()
        self.btn_save = QPushButton("Guardar Proyecto")
        self.btn_load = QPushButton("Cargar Proyecto")
        self.btn_save.clicked.connect(self._save)
        self.btn_load.clicked.connect(self._load)
        row4.addWidget(self.btn_save, 1)
        row4.addWidget(self.btn_load, 1)
        root.addLayout(row4)

        self._refresh_fields()
        self.ed_folder.textChanged.connect(self._on_fields_changed)
        self.ed_filename.textChanged.connect(self._on_fields_changed)

    def _refresh_fields(self):
        self.ed_folder.setText(self.dm.project_folder or "")
        self.ed_filename.setText(self.dm.project_filename or "")
        self.ed_path.setText(_norm_project_path(self.dm.project_folder, self.dm.project_filename))

    def _on_fields_changed(self):
        folder = self.ed_folder.text().strip()
        name = self.ed_filename.text().strip()
        if name.lower().endswith(".json"):
            name = name[:-5]
            self.ed_filename.blockSignals(True)
            self.ed_filename.setText(name)
            self.ed_filename.blockSignals(False)
        self.dm.set_project_location(folder, name)
        self.ed_path.setText(self.dm.file_path)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Selecciona carpeta del proyecto", self.dm.project_folder or "")
        if folder:
            self.ed_folder.setText(folder)

    def _choose_filename(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Nombre del fichero .ssaa",
                                                   self.dm.file_path or "", "SSAA (*{PROJECT_EXT});;JSON legacy (*.json)")
        if file_path:
            folder = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            filename = os.path.splitext(filename)[0]
            self.ed_folder.setText(folder)
            self.ed_filename.setText(filename)

    def _save(self):
        if not self.dm.has_project_file():
            dialogs.warn(self, "Archivo no definido", "Define carpeta y nombre de archivo primero.")
            return
        
        # ✅ NUEVO: forzar commit de ediciones pendientes (tablas/celdas en edición)
        try:
            w = self.window()
            if hasattr(w, "app_widget") and hasattr(w.app_widget, "commit_pending_edits"):
                w.app_widget.commit_pending_edits()
            elif hasattr(self.parent(), "commit_pending_edits"):
                self.parent().commit_pending_edits()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        res = run_guarded(lambda: self.dm.save_to_file(), parent=self, title="Error al guardar", user_message="No se pudo guardar el proyecto.")
        if res is not None:
            dialogs.info(self, "Guardado", "Proyecto guardado correctamente.")

    def _load(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto",
                                                   self.dm.project_folder or "", "SSAA (*{PROJECT_EXT});;JSON legacy (*.json)")
        if not file_path:
            return
        res = run_guarded(lambda: self.dm.load_from_file(file_path), parent=self, title="Error al cargar", user_message="No se pudo cargar el proyecto.")
        if res is None:
            return
        self.ed_folder.setText(os.path.dirname(file_path))
        self.ed_filename.setText(os.path.splitext(os.path.basename(file_path))[0])
        self.data_loaded.emit()
        dialogs.info(self, "Cargado", "Proyecto cargado.")
