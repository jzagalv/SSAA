# -*- coding: utf-8 -*-
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QListWidget, QListWidgetItem, QApplication
)
from PyQt5.QtCore import pyqtSignal, Qt, QUrl
from PyQt5.QtGui import QDesktopServices

from ui.common import dialogs
from ui.common.error_handler import run_guarded
from ui.common.recent_projects import RecentProjectsStore
from ui.utils.user_signals import connect_lineedit_user_live
from screens.base import ScreenBase
from data_model import _norm_project_path, PROJECT_EXT
from app.sections import Section

class FileScreen(ScreenBase):
    SECTION = Section.PROJECT
    data_loaded = pyqtSignal()

    def __init__(self, data_model, parent=None):
        super().__init__(data_model, parent)
        self.dm = self.data_model
        self._recents = RecentProjectsStore()
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
        btn_copy = QPushButton("Copiar")
        btn_open_folder = QPushButton("Abrir carpeta")
        btn_copy.clicked.connect(self._copy_path)
        btn_open_folder.clicked.connect(self._open_path_folder)
        row3.addWidget(btn_copy)
        row3.addWidget(btn_open_folder)
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

        root.addWidget(QLabel("Recientes:"))
        self.lst_recent = QListWidget()
        self.lst_recent.itemDoubleClicked.connect(lambda _: self._load_recent_selected())
        root.addWidget(self.lst_recent)

        row5 = QHBoxLayout()
        btn_clear_recent = QPushButton("Limpiar recientes")
        btn_clear_recent.clicked.connect(self._clear_recent)
        row5.addWidget(btn_clear_recent)
        row5.addStretch(1)
        root.addLayout(row5)

        self._refresh_fields()
        connect_lineedit_user_live(self.ed_folder, lambda _t: self._on_fields_changed())
        connect_lineedit_user_live(self.ed_filename, lambda _t: self._on_fields_changed())
        self._restore_persisted_defaults()
        self._refresh_recent_list()

    def _refresh_fields(self):
        self.ed_folder.setText(self.dm.project_folder or "")
        self.ed_filename.setText(self.dm.project_filename or "")
        self.ed_path.setText(_norm_project_path(self.dm.project_folder, self.dm.project_filename))

    def _restore_persisted_defaults(self) -> None:
        folder = (self.dm.project_folder or "").strip()
        name = (self.dm.project_filename or "").strip()
        if not folder:
            folder = self._recents.get_last_folder_ui("")
        if not name:
            name = self._recents.get_last_name_ui("")
        self.ed_folder.blockSignals(True)
        self.ed_filename.blockSignals(True)
        self.ed_folder.setText(folder)
        self.ed_filename.setText(name)
        self.ed_folder.blockSignals(False)
        self.ed_filename.blockSignals(False)
        self._on_fields_changed()

    def _refresh_recent_list(self) -> None:
        self.lst_recent.clear()
        paths = self._recents.list(existing_only=True, prune_missing=True)
        for file_path in paths:
            base = os.path.basename(file_path)
            folder = os.path.dirname(file_path)
            text = f"{base} — {folder}" if folder else file_path
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, file_path)
            item.setToolTip(file_path)
            self.lst_recent.addItem(item)

    def _push_recent(self, file_path: str) -> None:
        self._recents.push(file_path)
        self._refresh_recent_list()

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
        self._recents.set_last_folder_ui(folder)
        self._recents.set_last_name_ui(name)

    def _choose_folder(self):
        start_dir = self._recents.get_last_open_dir("") or self.dm.project_folder or ""
        folder = QFileDialog.getExistingDirectory(self, "Selecciona carpeta del proyecto", start_dir)
        if folder:
            self._recents.set_last_open_dir(folder)
            self.ed_folder.setText(folder)
            self._on_fields_changed()

    def _choose_filename(self):
        start_dir = self._recents.get_last_save_dir("") or self.dm.project_folder or ""
        start_name = self.dm.project_filename or "proyecto_ssaa"
        if not str(start_name).lower().endswith(PROJECT_EXT):
            start_name = f"{start_name}{PROJECT_EXT}"
        start_path = os.path.join(start_dir, start_name) if start_dir else start_name
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Nombre del fichero .ssaa",
            start_path,
            f"SSAA (*{PROJECT_EXT});;JSON legacy (*.json)",
        )
        if file_path:
            folder = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            filename = os.path.splitext(filename)[0]
            self._recents.set_last_save_dir(folder)
            self.ed_folder.setText(folder)
            self.ed_filename.setText(filename)
            self._on_fields_changed()

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
            if self.dm.file_path:
                folder = os.path.dirname(self.dm.file_path)
                self._recents.set_last_save_dir(folder)
                self._recents.set_last_open_dir(folder)
            self._push_recent(self.dm.file_path)
            dialogs.info(self, "Guardado", "Proyecto guardado correctamente.")

    def _load(self):
        start_dir = self._recents.get_last_open_dir("") or self.dm.project_folder or ""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir proyecto",
            start_dir,
            f"SSAA (*{PROJECT_EXT});;JSON legacy (*.json)",
        )
        if not file_path:
            return
        res = run_guarded(lambda: self.dm.load_from_file(file_path), parent=self, title="Error al cargar", user_message="No se pudo cargar el proyecto.")
        if res is None:
            return
        self.ed_folder.setText(os.path.dirname(file_path))
        self.ed_filename.setText(os.path.splitext(os.path.basename(file_path))[0])
        self._on_fields_changed()
        self._recents.set_last_open_dir(os.path.dirname(file_path))
        self._push_recent(file_path)
        self.data_loaded.emit()
        dialogs.info(self, "Cargado", "Proyecto cargado.")

    def _load_recent_selected(self) -> None:
        item = self.lst_recent.currentItem()
        if item is None:
            return
        file_path = str(item.data(Qt.UserRole) or "").strip()
        if not file_path:
            return
        if not os.path.exists(file_path):
            dialogs.warn(self, "Archivo no encontrado", "El archivo seleccionado ya no existe.")
            self._refresh_recent_list()
            return
        res = run_guarded(lambda: self.dm.load_from_file(file_path), parent=self, title="Error al cargar", user_message="No se pudo cargar el proyecto.")
        if res is None:
            return
        self.ed_folder.setText(os.path.dirname(file_path))
        self.ed_filename.setText(os.path.splitext(os.path.basename(file_path))[0])
        self._on_fields_changed()
        self._recents.set_last_open_dir(os.path.dirname(file_path))
        self.data_loaded.emit()
        dialogs.info(self, "Cargado", "Proyecto cargado.")
        self._push_recent(file_path)

    def _clear_recent(self) -> None:
        self._recents.clear()
        self._refresh_recent_list()

    def _copy_path(self) -> None:
        path = self.ed_path.text().strip()
        if not path:
            dialogs.warn(self, "Ruta vacía", "No hay ruta para copiar.")
            return
        QApplication.clipboard().setText(path)
        dialogs.info(self, "Copiado", "Ruta copiada al portapapeles.")

    def _open_path_folder(self) -> None:
        path = self.ed_path.text().strip()
        folder = os.path.dirname(path)
        if not folder or not os.path.isdir(folder):
            dialogs.warn(self, "Carpeta no disponible", "La carpeta de la ruta actual no existe.")
            return
        ok = QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        if not ok:
            dialogs.warn(self, "No se pudo abrir", "No fue posible abrir la carpeta.")
