from PyQt5.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QComboBox,
)
from PyQt5.QtCore import pyqtSignal, Qt

from screens.base import ScreenBase
from app.sections import Section
from ui.table_utils import make_table_sortable
from ui.utils.table_utils import configure_table_autoresize
from screens.project.location_controller import LocationController


class LocationScreen(ScreenBase):
    SECTION = Section.INSTALACIONES
    cabinets_updated = pyqtSignal()

    def __init__(self, data_model):
        super().__init__(data_model, parent=None)
        self.controller = LocationController(self.data_model)
        self.initUI()
        self.actualizar_combobox_salas()
        self.actualizar_tablas()

    # ------------------------------
    # Helpers internos
    # ------------------------------
    @staticmethod
    def _sala_parts(sala):
        if isinstance(sala, (tuple, list)) and len(sala) >= 2:
            return sala[0] or "", sala[1] or ""
        if isinstance(sala, dict):
            return sala.get("tag", "") or "", sala.get("nombre", "") or ""
        return "", ""

    def _limpiar_inputs_sala(self):
        self.input_tag_sala.clear()
        self.input_nombre_sala.clear()
        self.input_tag_sala.setFocus()

    def _limpiar_inputs_gabinete(self):
        self.input_tag_gabinete.clear()
        self.input_nombre_gabinete.clear()
        self.combo_salas.setCurrentIndex(-1)
        self.input_tag_gabinete.setFocus()

    # ------------------------------
    # UI
    # ------------------------------
    def initUI(self):
        layout = QVBoxLayout()

        # ===== Ubicaciones =====
        sala_layout = QVBoxLayout()

        tag_sala_layout = QHBoxLayout()
        tag_sala_layout.addWidget(QLabel("TAG Ubicación:"))
        self.input_tag_sala = QLineEdit()
        self.input_tag_sala.setPlaceholderText("Ej: SALA-01")
        tag_sala_layout.addWidget(self.input_tag_sala)

        nombre_sala_layout = QHBoxLayout()
        nombre_sala_layout.addWidget(QLabel("Nombre Ubicación:"))
        self.input_nombre_sala = QLineEdit()
        self.input_nombre_sala.setPlaceholderText("Ej: Patio / Sala / Edificio")
        nombre_sala_layout.addWidget(self.input_nombre_sala)

        btn_sala_layout = QHBoxLayout()
        btn_agregar_sala = QPushButton("Agregar Ubicación")
        btn_agregar_sala.clicked.connect(self.agregar_sala)
        btn_editar_sala = QPushButton("Editar Ubicación")
        btn_editar_sala.clicked.connect(self.editar_sala)
        btn_eliminar_sala = QPushButton("Eliminar Ubicación")
        btn_eliminar_sala.clicked.connect(self.eliminar_sala)

        btn_sala_layout.addWidget(btn_agregar_sala)
        btn_sala_layout.addWidget(btn_editar_sala)
        btn_sala_layout.addWidget(btn_eliminar_sala)

        sala_layout.addLayout(tag_sala_layout)
        sala_layout.addLayout(nombre_sala_layout)
        sala_layout.addLayout(btn_sala_layout)
        layout.addLayout(sala_layout)

        self.tabla_salas = QTableWidget()
        self.tabla_salas.setColumnCount(2)
        self.tabla_salas.setHorizontalHeaderLabels(["TAG", "Nombre"])
        configure_table_autoresize(self.tabla_salas)
        make_table_sortable(self.tabla_salas)
        self.tabla_salas.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_salas.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.tabla_salas)
        self.tabla_salas.itemSelectionChanged.connect(self._on_select_sala)

        # ===== Gabinetes =====
        gabinete_layout = QVBoxLayout()

        tag_gabinete_layout = QHBoxLayout()
        tag_gabinete_layout.addWidget(QLabel("TAG Gabinete:"))
        self.input_tag_gabinete = QLineEdit()
        self.input_tag_gabinete.setPlaceholderText("Ej: GAB-001")
        tag_gabinete_layout.addWidget(self.input_tag_gabinete)

        nombre_gabinete_layout = QHBoxLayout()
        nombre_gabinete_layout.addWidget(QLabel("Nombre Gabinete:"))
        self.input_nombre_gabinete = QLineEdit()
        self.input_nombre_gabinete.setPlaceholderText("Ej: Tablero Fuerza")
        nombre_gabinete_layout.addWidget(self.input_nombre_gabinete)

        self.combo_salas = QComboBox()
        self.combo_salas.setPlaceholderText("Seleccione una ubicación")

        btn_gabinete_layout = QHBoxLayout()
        btn_agregar_gabinete = QPushButton("Agregar Gabinete")
        btn_agregar_gabinete.clicked.connect(self.agregar_gabinete)
        btn_editar_gabinete = QPushButton("Editar Gabinete")
        btn_editar_gabinete.clicked.connect(self.editar_gabinete)
        btn_eliminar_gabinete = QPushButton("Eliminar Gabinete")
        btn_eliminar_gabinete.clicked.connect(self.eliminar_gabinete)

        btn_gabinete_layout.addWidget(btn_agregar_gabinete)
        btn_gabinete_layout.addWidget(btn_editar_gabinete)
        btn_gabinete_layout.addWidget(btn_eliminar_gabinete)

        gabinete_layout.addLayout(tag_gabinete_layout)
        gabinete_layout.addLayout(nombre_gabinete_layout)
        gabinete_layout.addWidget(self.combo_salas)
        gabinete_layout.addLayout(btn_gabinete_layout)
        layout.addLayout(gabinete_layout)

        self.tabla_gabinetes = QTableWidget()
        self.tabla_gabinetes.setColumnCount(5)
        self.tabla_gabinetes.setHorizontalHeaderLabels(
            ["TAG", "Nombre", "Ubicación", "TD/TG", "Fuente de Alimentación"]
        )
        configure_table_autoresize(self.tabla_gabinetes)
        self.tabla_gabinetes.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_gabinetes.setSelectionMode(QTableWidget.SingleSelection)
        make_table_sortable(self.tabla_gabinetes)
        layout.addWidget(self.tabla_gabinetes)
        self.tabla_gabinetes.itemChanged.connect(self._on_gabinete_item_changed)
        self.tabla_gabinetes.itemSelectionChanged.connect(self._on_select_gabinete)

        self.setLayout(layout)

    # ------------------------------
    # Actualizaciones de UI
    # ------------------------------
    def actualizar_tablas(self):
        self.actualizar_tabla_salas()
        self.actualizar_tabla_gabinetes()
        self.actualizar_combobox_salas()

    def actualizar_tabla_salas(self):
        self.tabla_salas.blockSignals(True)
        try:
            filas = len(self.data_model.salas)
            self.tabla_salas.setRowCount(filas)
            for row, sala in enumerate(self.data_model.salas):
                tag, nombre = self._sala_parts(sala)
                self.tabla_salas.setItem(row, 0, QTableWidgetItem(tag))
                self.tabla_salas.setItem(row, 1, QTableWidgetItem(nombre))
            self.tabla_salas.clearSelection()
        finally:
            self.tabla_salas.blockSignals(False)

    def actualizar_tabla_gabinetes(self):
        self.tabla_gabinetes.blockSignals(True)
        try:
            filas = len(self.data_model.gabinetes)
            self.tabla_gabinetes.setRowCount(filas)
            for row, gabinete in enumerate(self.data_model.gabinetes):
                tag = gabinete.get("tag", "")
                nombre = gabinete.get("nombre", "")
                sala = gabinete.get("sala", "")
                self.tabla_gabinetes.setItem(row, 0, QTableWidgetItem(tag))
                self.tabla_gabinetes.setItem(row, 1, QTableWidgetItem(nombre))
                self.tabla_gabinetes.setItem(row, 2, QTableWidgetItem(sala))
                it = QTableWidgetItem("")
                it.setFlags((it.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
                it.setCheckState(Qt.Checked if bool(gabinete.get("is_board", False)) else Qt.Unchecked)
                self.tabla_gabinetes.setItem(row, 3, it)
                it2 = QTableWidgetItem("")
                it2.setFlags((it2.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
                it2.setCheckState(
                    Qt.Checked if bool(gabinete.get("is_energy_source", False)) else Qt.Unchecked
                )
                self.tabla_gabinetes.setItem(row, 4, it2)
            self.tabla_gabinetes.clearSelection()
        finally:
            self.tabla_gabinetes.blockSignals(False)

    def actualizar_combobox_salas(self):
        self.combo_salas.blockSignals(True)
        self.combo_salas.clear()
        for sala in self.data_model.salas:
            tag, nombre = self._sala_parts(sala)
            label = f"{tag} - {nombre}" if nombre else tag
            self.combo_salas.addItem(label, tag)
        self.combo_salas.setCurrentIndex(-1)
        self.combo_salas.blockSignals(False)

    # ------------------------------
    # Handlers de selección
    # ------------------------------
    def _on_select_sala(self):
        fila = self.tabla_salas.currentRow()
        if fila < 0 or fila >= len(self.data_model.salas):
            return
        tag, nombre = self._sala_parts(self.data_model.salas[fila])
        self.input_tag_sala.setText(tag)
        self.input_nombre_sala.setText(nombre)

    def _on_select_gabinete(self):
        fila = self.tabla_gabinetes.currentRow()
        if fila < 0 or fila >= len(self.data_model.gabinetes):
            return
        g = self.data_model.gabinetes[fila]
        self.input_tag_gabinete.setText(g.get("tag", ""))
        self.input_nombre_gabinete.setText(g.get("nombre", ""))
        sala_label = g.get("sala", "")
        idx = self.combo_salas.findText(sala_label, Qt.MatchExactly)
        if idx >= 0:
            self.combo_salas.setCurrentIndex(idx)

    # ------------------------------
    # Salas y gabinetes (CRUD)
    # ------------------------------
    def _on_gabinete_item_changed(self, item: QTableWidgetItem):
        if item is None:
            return
        row = item.row()
        col = item.column()
        if row < 0:
            return

        if col == 0:
            field = "tag"
            value = item.text()
        elif col == 1:
            field = "nombre"
            value = item.text()
        elif col == 2:
            field = "sala"
            value = item.text()
        elif col == 3:
            field = "is_board"
            value = item.checkState() == Qt.Checked
        elif col == 4:
            field = "is_energy_source"
            value = item.checkState() == Qt.Checked
        else:
            return

        try:
            self.controller.update_gabinete_field(row, field, value)
        except ValueError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            self.actualizar_tabla_gabinetes()
            return

        self.actualizar_combobox_salas()

    def agregar_sala(self):
        tag = self.input_tag_sala.text().strip()
        nombre = self.input_nombre_sala.text().strip()
        try:
            self.controller.add_ubicacion(tag, nombre)
        except ValueError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self.actualizar_tablas()
        self._limpiar_inputs_sala()

    def editar_sala(self):
        fila = self.tabla_salas.currentRow()
        tag = self.input_tag_sala.text().strip()
        nombre = self.input_nombre_sala.text().strip()
        try:
            self.controller.edit_ubicacion(fila, tag, nombre)
        except ValueError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self.actualizar_tablas()
        self._limpiar_inputs_sala()

    def eliminar_sala(self):
        fila = self.tabla_salas.currentRow()
        try:
            self.controller.delete_ubicacion(fila)
        except ValueError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self.actualizar_tablas()
        self.cabinets_updated.emit()

    def agregar_gabinete(self):
        tag = self.input_tag_gabinete.text().strip()
        nombre = self.input_nombre_gabinete.text().strip()
        ubic_tag = self.combo_salas.currentData()
        try:
            self.controller.add_gabinete(tag, nombre, ubic_tag)
        except ValueError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self.actualizar_tablas()
        self.cabinets_updated.emit()
        self._limpiar_inputs_gabinete()

    def editar_gabinete(self):
        fila = self.tabla_gabinetes.currentRow()
        tag = self.input_tag_gabinete.text().strip()
        nombre = self.input_nombre_gabinete.text().strip()
        ubic_tag = self.combo_salas.currentData()
        try:
            self.controller.edit_gabinete(fila, tag, nombre, ubic_tag)
        except ValueError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self.actualizar_tablas()
        self.cabinets_updated.emit()
        self._limpiar_inputs_gabinete()

    def eliminar_gabinete(self):
        fila = self.tabla_gabinetes.currentRow()
        try:
            self.controller.delete_gabinete(fila)
        except ValueError as exc:
            QMessageBox.warning(self, "Error", str(exc))
            return
        self.actualizar_tablas()
        self.cabinets_updated.emit()

    # --- ScreenBase hooks ---
    def load_from_model(self):
        """Load UI from DataModel (ScreenBase hook)."""
        try:
            self.actualizar_tablas()
        except Exception:
            import logging

            logging.getLogger(__name__).debug("Ignored exception (best-effort).", exc_info=True)

    def save_to_model(self):
        """Persist UI edits to DataModel (ScreenBase hook)."""
        pass

