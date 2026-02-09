# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtGui import QDoubleValidator, QIntValidator

from PyQt5.QtCore import Qt, pyqtSignal

from screens.base import ScreenBase
from app.sections import Section

PROJ_KEYS = [
    "cliente", "project_number", "tag_room",
    "doc_isep", "doc_cliente", "altura",
    "tension_monofasica", "tension_trifasica",
    "max_voltaje", "min_voltaje", "frecuencia",
    "tension_nominal", "max_voltaje_cc", "min_voltaje_cc",
    "num_cargadores", "num_bancos", "porcentaje_utilizacion", "tiempo_autonomia",
]


class MainScreen(ScreenBase):
    SECTION = Section.PROJECT
    porcentaje_util_changed = pyqtSignal(float)

    def __init__(self, data_model):
        super().__init__(data_model, parent=None)
        self.inputs = {}  # key -> QLineEdit
        self.initUI()
        self.setup_validators()

    # ----- helpers de binding -----
    def _bind_line(self, key: str, line: QLineEdit):
        """Vincula un QLineEdit con data_model.proyecto[key] y marca dirty en cambios."""
        self.inputs[key] = line

        def on_change(text):
            # Evitar ensuciar el proyecto por refrescos/cargas o si el
            # valor realmente no cambio.
            if getattr(self.data_model, "_ui_refreshing", False):
                return
            old = self.data_model.proyecto.get(key, "")
            if old == text:
                return
            self.data_model.proyecto[key] = text
            self.data_model.mark_dirty(True)

            # si es el % de utilizacion, avisamos al resto de pantallas
            if key == "porcentaje_utilizacion":
                value = self._to_float(text, default=0.0)
                self.porcentaje_util_changed.emit(value)

        line.textChanged.connect(on_change)

    @staticmethod
    def _to_float(val, default=0.0):
        if val is None:
            return default
        s = str(val).strip().replace(",", ".")
        if not s:
            return default
        try:
            return float(s)
        except ValueError:
            return default

    def set_pct_from_outside(self, value: float):
        """
        Actualiza el QLineEdit de % Utilizacion desde otra pantalla,
        sin disparar recursivamente textChanged.
        """
        txt = f"{float(value):.2f}"
        if self.ed_util.text() == txt:
            return

        # evitar bucles de señales
        self.ed_util.blockSignals(True)
        self.ed_util.setText(txt)
        self.ed_util.blockSignals(False)

        # aseguramos que el modelo se mantenga coherente
        self.data_model.proyecto["porcentaje_utilizacion"] = txt
        # Este campo se ajusta por recalculo/propagacion desde otras
        # pantallas, por lo que NO debe marcar el proyecto como 'dirty'.
        # (si el usuario lo edita directamente, se marca dirty en _bind_line)

    # ----- UI -----
    def initUI(self):
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)

        # === Datos del Proyecto ===
        g_proy = QGroupBox("Datos del Proyecto")
        g_proy.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        f_proy = QFormLayout()
        f_proy.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        f_proy.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.ed_cliente = QLineEdit();                self._bind_line("cliente", self.ed_cliente)
        f_proy.addRow("Cliente:", self.ed_cliente)

        self.ed_num_proy = QLineEdit();               self._bind_line("project_number", self.ed_num_proy)
        f_proy.addRow("N° Proyecto:", self.ed_num_proy)

        self.ed_tag_room = QLineEdit();               self._bind_line("tag_room", self.ed_tag_room)
        f_proy.addRow("TAG Sala:", self.ed_tag_room)

        self.ed_doc_isep = QLineEdit();               self._bind_line("doc_isep", self.ed_doc_isep)
        f_proy.addRow("Doc. I-SEP:", self.ed_doc_isep)

        self.ed_doc_cliente = QLineEdit();            self._bind_line("doc_cliente", self.ed_doc_cliente)
        f_proy.addRow("Doc. Cliente:", self.ed_doc_cliente)

        self.ed_altura = QLineEdit();                 self._bind_line("altura", self.ed_altura)
        f_proy.addRow("Altura (msnm):", self.ed_altura)

        g_proy.setLayout(f_proy)
        content_layout.addWidget(g_proy)

        # === Sistema CA ===
        g_ca = QGroupBox("Sistema CA")
        g_ca.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        f_ca = QFormLayout()
        f_ca.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        f_ca.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.ed_v_mono = QLineEdit();                 self._bind_line("tension_monofasica", self.ed_v_mono)
        f_ca.addRow("Tensión Monofásica (V):", self.ed_v_mono)

        self.ed_v_tri = QLineEdit();                  self._bind_line("tension_trifasica", self.ed_v_tri)
        f_ca.addRow("Tensión Trifásica (V):", self.ed_v_tri)

        self.ed_vmax = QLineEdit();                   self._bind_line("max_voltaje", self.ed_vmax)
        f_ca.addRow("Tensión Máxima (%):", self.ed_vmax)

        self.ed_vmin = QLineEdit();                   self._bind_line("min_voltaje", self.ed_vmin)
        f_ca.addRow("Tensión Mínima (%):", self.ed_vmin)

        self.ed_freq = QLineEdit();                   self._bind_line("frecuencia", self.ed_freq)
        f_ca.addRow("Frecuencia (Hz):", self.ed_freq)

        g_ca.setLayout(f_ca)
        content_layout.addWidget(g_ca)

        # === Sistema CC ===
        g_cc = QGroupBox("Sistema CC")
        g_cc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        f_cc = QFormLayout()
        f_cc.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        f_cc.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.ed_nom = QLineEdit();                    self._bind_line("tension_nominal", self.ed_nom)
        f_cc.addRow("Tensión Nominal (V):", self.ed_nom)

        self.ed_cc_max = QLineEdit();                 self._bind_line("max_voltaje_cc", self.ed_cc_max)
        f_cc.addRow("Tensión Máxima (%):", self.ed_cc_max)

        self.ed_cc_min = QLineEdit();                 self._bind_line("min_voltaje_cc", self.ed_cc_min)
        f_cc.addRow("Tensión Mínima (%):", self.ed_cc_min)

        self.ed_carg = QLineEdit();                   self._bind_line("num_cargadores", self.ed_carg)
        f_cc.addRow("N° Cargadores:", self.ed_carg)

        self.ed_bancos = QLineEdit();                 self._bind_line("num_bancos", self.ed_bancos)
        f_cc.addRow("N° Bancos:", self.ed_bancos)

        self.ed_util = QLineEdit();                   self._bind_line("porcentaje_utilizacion", self.ed_util)
        # f_cc.addRow("% Utilización:", self.ed_util)

        self.aut_time = QLineEdit();                  self._bind_line("tiempo_autonomia", self.aut_time)
        f_cc.addRow("Tiempo de Autonomía [h]:", self.aut_time)

        g_cc.setLayout(f_cc)
        content_layout.addWidget(g_cc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

        # Carga inicial de datos del modelo
        self.load_data()

    # ----- Carga desde el modelo -----
    def load_data(self):
        p = self.data_model.proyecto or {}

        def _set(line: QLineEdit, v):
            line.setText("" if v is None else str(v))

        _set(self.ed_cliente, p.get("cliente", ""))
        _set(self.ed_num_proy, p.get("project_number", ""))
        _set(self.ed_tag_room, p.get("tag_room", ""))
        _set(self.ed_doc_isep, p.get("doc_isep", ""))
        _set(self.ed_doc_cliente, p.get("doc_cliente", ""))
        _set(self.ed_altura, p.get("altura", ""))

        _set(self.ed_v_mono, p.get("tension_monofasica", ""))
        _set(self.ed_v_tri, p.get("tension_trifasica", ""))
        _set(self.ed_vmax, p.get("max_voltaje", ""))
        _set(self.ed_vmin, p.get("min_voltaje", ""))
        _set(self.ed_freq, p.get("frecuencia", ""))

        _set(self.ed_nom, p.get("tension_nominal", ""))
        _set(self.ed_cc_max, p.get("max_voltaje_cc", ""))
        _set(self.ed_cc_min, p.get("min_voltaje_cc", ""))
        _set(self.ed_carg, p.get("num_cargadores", ""))
        _set(self.ed_bancos, p.get("num_bancos", ""))
        _set(self.ed_util, p.get("porcentaje_utilizacion", ""))
        _set(self.aut_time, p.get("tiempo_autonomia", ""))

    def setup_validators(self):
        self.ed_altura.setValidator(QDoubleValidator(0, 10000, 2, self))
        self.ed_vmax.setValidator(QDoubleValidator(0, 100, 2, self))
        self.ed_vmin.setValidator(QDoubleValidator(0, 100, 2, self))
        self.ed_cc_max.setValidator(QDoubleValidator(0, 100, 2, self))
        self.ed_cc_min.setValidator(QDoubleValidator(0, 100, 2, self))
        self.ed_carg.setValidator(QIntValidator(0, 100, self))
        self.ed_bancos.setValidator(QIntValidator(0, 100, self))
        self.ed_util.setValidator(QDoubleValidator(0, 100, 2, self))
        self.aut_time.setValidator(QDoubleValidator(0, 100, 2, self))

    # --- ScreenBase hooks ---
    def load_from_model(self):
        """Load UI fields from DataModel (ScreenBase hook)."""
        try:
            self.load_data()
        except Exception:
            import logging
            logging.getLogger(__name__).debug("Ignored exception (best-effort).", exc_info=True)

    def save_to_model(self):
        """Persist UI edits to DataModel (ScreenBase hook)."""
        # This screen writes through on-change bindings; keep as no-op.
        pass
