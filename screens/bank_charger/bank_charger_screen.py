# -*- coding: utf-8 -*-
"""
BankChargerSizingScreen

Reordenamiento "según norma":
- TAB 1: Datos del sistema + Comprobación
- TAB 2:
    [Izquierda: Tabla Perfil de cargas]   [Derecha: Tabla Ciclo de trabajo (Table A.1)]
    [               Abajo: Gráfico ciclo de trabajo (duty cycle)                 ]
- TAB 3:
    Tabla completa "Cell sizing worksheet" (IEEE 485) con secciones y subtotales.

IEEE 485 worksheet (TAB 3):
- Se arma desde la Tabla "Ciclo de trabajo" (periodos A1..An y "R").
- A1..An: corresponden a los periodos del duty cycle (Total amperes por periodo).
- M1..Mn: corresponden a la duración de cada periodo (min).
- Change in load: Ai - A(i-1) (A0=0).
- Time to end of section (T): sum_{j=i..s} Mj en la sección s.
- Columna (6) Kt: editable por el usuario. Se guarda en proyecto['ieee485_kt'].
- Columnas (7) Pos/Neg: (3) * (6). Neg queda negativa si (3) < 0.
- Sub Tot: suma por sección de Pos y Neg.
- Total: Pos + Neg (neto) en Pos Values; Neg Values = '***' (como en el ejemplo).

Nota: PyQt5 no tiene "tablas con layout de texto" como el PDF, pero replicamos la estructura
con filas de encabezado por sección, filas de datos, y filas Sub Tot/Total (con celdas combinadas).
"""

import math
import re

from screens.base import ScreenBase
from app.sections import Section

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem,
    QComboBox, QPushButton, QInputDialog, QMessageBox, QLabel,
    QTabWidget, QSplitter
)
from ui.utils.table_utils import configure_table_autoresize
from ui.delegates.editable_bg_delegate import EditableBgDelegate

from PyQt5.QtGui import QColor
from .widgets.duty_cycle_plot_widget import DutyCyclePlotWidget
from .bank_charger_export import export_all_one_click, save_widget_screenshot
from .bank_charger_controller import BankChargerController
from PyQt5.QtWidgets import QAbstractItemView

from services.ssaa_engine import SSAAEngine

from domain.cc_consumption import (
    get_model_gabinetes as cc_get_model_gabinetes,
    compute_cc_profile_totals,
    compute_momentary_scenarios,
    compute_momentary_from_permanents,
)

import logging
from ui.theme import get_theme_token

DURACION_MIN_GRAFICA_MIN = 10.0
CODE_L1 = "L1"
CODE_LAL = "L(al)"


def _theme_color(token: str, fallback: str) -> QColor:
    return QColor(get_theme_token(token, fallback))


class BankChargerSizingScreen(ScreenBase):
    SECTION = Section.BANK_CHARGER
    def __init__(self, data_model, parent=None):
        super().__init__(data_model, parent)
        self.data_model = data_model
        self._updating = False

        # cache: periodos A/M desde ciclo de trabajo (A1..An, M1..Mn)
        self._cycle_periods_cache = []  # list of dict: {"A":float,"M":float,"loads":str}

        self._chart_timer = QTimer(self)
        self._chart_timer.setSingleShot(True)
        self._chart_timer.timeout.connect(self._update_profile_chart)

        self._build_ui()
        self._controller = BankChargerController(self)
        self.persistence = self._controller.persistence
        self._perfil_loaded = False
        self._ieee_loaded = False
        self._seleccion_loaded = False
        self._resumen_loaded = False
        self._pending_inner_tab_refresh = False
        if getattr(self, "inner_tabs", None) is not None:
            self.inner_tabs.currentChanged.connect(self._on_inner_tab_changed)
            self._schedule_active_inner_tab_refresh()
        self._fill_datos_sistema()
        self._fill_comprobacion()

        # IEEE 485: estructura + carga Kt guardados
        self._build_ieee485_table_structure()

        self._user_vcell_sel = None
        stored = self._proj_value("v_celda_sel_usuario")
        if stored:
            try:
                self._user_vcell_sel = float(str(stored).replace(",", "."))
            except ValueError:
                self._user_vcell_sel = None

        self._install_vcell_combo()
        self._load_modes_from_project()

        self._connect_signals()
        # Startup policy: NEVER run heavy calculations nor show blocking dialogs during __init__.
        # The SectionOrchestrator will refresh/recalculate after a project is loaded or when sections change.
        self._render_startup_state()

        self._schedule_updates()
        self._refresh_battery_selector()
        self._refresh_battery_warning()

    def _render_startup_state(self) -> None:
        """Render a safe initial UI state without running calculations.

        At app startup the project may be empty. We must not:
          - Trigger engine computations
          - Show blocking QMessageBox popups

        The SectionOrchestrator will refresh/recalculate after project load or edits.
        """
        try:
            # Selection tables: explicit empty-state rows.
            for tbl in (getattr(self, "tbl_sel_bank", None), getattr(self, "tbl_sel_charger", None)):
                if tbl is None:
                    continue
                tbl.setRowCount(0)

            def _add_kv(tbl, k, v):
                if tbl is None:
                    return
                r = tbl.rowCount()
                tbl.insertRow(r)
                from PyQt5.QtWidgets import QTableWidgetItem
                tbl.setItem(r, 0, QTableWidgetItem(str(k)))
                tbl.setItem(r, 1, QTableWidgetItem(str(v)))

            _add_kv(getattr(self, "tbl_sel_bank", None), "Estado", "Proyecto no cargado (sin cálculo)")
            _add_kv(getattr(self, "tbl_sel_charger", None), "Estado", "Proyecto no cargado (sin cálculo)")

            # Clear cached bundle to force a clean recompute after project load.
            self._bc_bundle = None
            self._last_engine_issues = []
        except Exception:
            import logging
            logging.getLogger(__name__).debug("Startup state rendering failed (ignored).", exc_info=True)

    def _build_ui(self):
        self.setObjectName("bank_black_screen")
        main_layout = QVBoxLayout(self)
        self.inner_tabs = QTabWidget()
        main_layout.addWidget(self.inner_tabs)

        # ---- TAB 1 ----
        page_sys = QWidget()
        page_sys_layout = QVBoxLayout(page_sys)

        top_row = QHBoxLayout()

        self.grp_datos = QGroupBox("Datos del Sistema")
        v_datos = QVBoxLayout()
        vpc_mode_row = QHBoxLayout()
        vpc_mode_row.addWidget(QLabel("Vpc final"))
        self.cmb_vpc_mode = QComboBox()
        self.cmb_vpc_mode.addItems(["Auto", "Manual"])
        vpc_mode_row.addWidget(self.cmb_vpc_mode)
        vpc_mode_row.addStretch()
        self.tbl_datos = QTableWidget()
        self.tbl_datos.setColumnCount(2)
        self.tbl_datos.setHorizontalHeaderLabels(["Característica", "Valor"])
        self.tbl_datos.verticalHeader().setVisible(False)
        self.tbl_datos.setItemDelegate(EditableBgDelegate(self.tbl_datos))
        configure_table_autoresize(self.tbl_datos)
        self.btn_cap_tbl_datos = QPushButton("Guardar captura")
        self.btn_cap_tbl_datos.clicked.connect(lambda: self._save_widget_screenshot(self.tbl_datos, "tabla_datos_del_sistema"))
        v_datos.addWidget(self.btn_cap_tbl_datos)
        v_datos.addLayout(vpc_mode_row)
        v_datos.addWidget(self.tbl_datos)
        self.grp_datos.setLayout(v_datos)

        self.grp_comp = QGroupBox("Comprobación")
        v_comp = QVBoxLayout()
        cells_mode_row = QHBoxLayout()
        cells_mode_row.addWidget(QLabel("N° celdas"))
        self.cmb_cells_mode = QComboBox()
        self.cmb_cells_mode.addItems(["Auto", "Manual"])
        cells_mode_row.addWidget(self.cmb_cells_mode)
        cells_mode_row.addStretch()
        self.tbl_comp = QTableWidget()
        self.tbl_comp.setColumnCount(2)
        self.tbl_comp.setHorizontalHeaderLabels(["Parámetro", "Valor"])
        self.tbl_comp.setItemDelegate(EditableBgDelegate(self.tbl_comp))
        configure_table_autoresize(self.tbl_comp)
        self.tbl_comp.verticalHeader().setVisible(False)
        self.btn_cap_tbl_comp = QPushButton("Guardar captura")
        self.btn_cap_tbl_comp.clicked.connect(lambda: self._save_widget_screenshot(self.tbl_comp, "tabla_comprobacion"))
        v_comp.addWidget(self.btn_cap_tbl_comp)
        v_comp.addLayout(cells_mode_row)
        v_comp.addWidget(self.tbl_comp)
        self.grp_comp.setLayout(v_comp)

        top_row.addWidget(self.grp_datos, 2)
        top_row.addWidget(self.grp_comp, 1)
        # Que el contenido aproveche el alto disponible (evita grandes espacios
        # en blanco en resoluciones grandes)
        page_sys_layout.addLayout(top_row, 1)

        self.inner_tabs.addTab(page_sys, "Datos y comprobación")

        # ---- TAB 2 ----
        page_profile = QWidget()
        page_profile_layout = QVBoxLayout(page_profile)

        split_v = QSplitter(Qt.Vertical)
        split_top = QSplitter(Qt.Horizontal)

        # Izquierda: perfil
        self.grp_cargas = QGroupBox("Tabla – Perfil de cargas")
        v_cargas = QVBoxLayout()

        btn_row = QHBoxLayout()
        self.btn_add_from_scenario = QPushButton("Agregar desde escenario C.C.")
        self.btn_del_area = QPushButton("Eliminar carga seleccionada")
        btn_row.addWidget(self.btn_add_from_scenario)
        btn_row.addWidget(self.btn_del_area)
        btn_row.addStretch()
        v_cargas.addLayout(btn_row)

        self.tbl_cargas = QTableWidget()
        self.tbl_cargas.setColumnCount(6)
        self.tbl_cargas.setHorizontalHeaderLabels(
            ["Ítem", "Descripción", "P [W]", "I [A]", "Inicio [min]", "Duración [min]"]
        )
        configure_table_autoresize(self.tbl_cargas)
        self.tbl_cargas.verticalHeader().setVisible(False)
        self.btn_cap_tbl_cargas = QPushButton("Guardar captura de tabla")
        self.btn_cap_tbl_cargas.clicked.connect(lambda: self._save_widget_screenshot(self.tbl_cargas, "tabla_perfil_de_cargas"))
        btn_row.addWidget(self.btn_cap_tbl_cargas)
        v_cargas.addWidget(self.tbl_cargas)
        self.grp_cargas.setLayout(v_cargas)

        # Derecha: ciclo
        self.grp_cycle = QGroupBox("Tabla – Ciclo de trabajo")
        v_cycle = QVBoxLayout()
        self.tbl_cycle = QTableWidget()
        self.tbl_cycle.setColumnCount(4)
        self.tbl_cycle.setHorizontalHeaderLabels(["Periodo", "Cargas", "Corriente Total", "Duración [min]"])
        configure_table_autoresize(self.tbl_cycle)
        self.tbl_cycle.verticalHeader().setVisible(False)
        self.btn_cap_tbl_cycle = QPushButton("Guardar captura de tabla")
        self.btn_cap_tbl_cycle.clicked.connect(lambda: self._save_widget_screenshot(self.tbl_cycle, "tabla_ciclo_de_trabajo"))
        v_cycle.addWidget(self.btn_cap_tbl_cycle)
        v_cycle.addWidget(self.tbl_cycle)
        self.grp_cycle.setLayout(v_cycle)

        split_top.addWidget(self.grp_cargas)
        split_top.addWidget(self.grp_cycle)
        split_top.setStretchFactor(0, 2)
        split_top.setStretchFactor(1, 1)
        split_top.setSizes([800, 400])

        split_v.addWidget(split_top)

        # Abajo: gráfico
        self.grp_chart = QGroupBox("Gráfico ciclo de trabajo")
        vchart = QVBoxLayout(self.grp_chart)
        self.plot_widget = DutyCyclePlotWidget(self)
        self.btn_cap_chart = QPushButton("Guardar captura del gráfico")
        self.btn_cap_chart.clicked.connect(lambda: self._save_widget_screenshot(self.plot_widget, "grafico_ciclo_de_trabajo"))
        vchart.addWidget(self.btn_cap_chart)
        vchart.addWidget(self.plot_widget)

        split_v.addWidget(self.grp_chart)
        split_v.setStretchFactor(0, 3)
        split_v.setStretchFactor(1, 2)

        page_profile_layout.addWidget(split_v)
        self.inner_tabs.addTab(page_profile, "Perfil de cargas")

        # ---- TAB 3: IEEE 485 worksheet ----
        page_ieee = QWidget()
        page_ieee_layout = QVBoxLayout(page_ieee)

        self.grp_ieee = QGroupBox("Tabla – IEEE 485 Cell sizing worksheet")
        v_ieee = QVBoxLayout(self.grp_ieee)

        self.tbl_ieee = QTableWidget()
        self.tbl_ieee.setColumnCount(8)
        self.tbl_ieee.setHorizontalHeaderLabels([
            "Period",
            "Load (amperes)",
            "Change in Load (amperes)",
            "Duration of Period (minutes)",
            "Time to End of Section (minutes)",
            "(6) K Factor (Kt)",
            "Pos Values",
            "Neg Values",
        ])
        configure_table_autoresize(self.tbl_ieee)
        self.tbl_ieee.verticalHeader().setVisible(False)

        self.btn_cap_tbl_ieee = QPushButton("Guardar captura de tabla")
        self.btn_cap_tbl_ieee.clicked.connect(lambda: self._save_widget_screenshot(self.tbl_ieee, "tabla_ieee_485"))
        v_ieee.addWidget(self.btn_cap_tbl_ieee)
        v_ieee.addWidget(self.tbl_ieee)
        page_ieee_layout.addWidget(self.grp_ieee)
        self.inner_tabs.addTab(page_ieee, "IEEE 485")

        # ---- TAB 4: Selección Banco + Cargador ----
        page_sel = QWidget()
        page_sel_layout = QVBoxLayout(page_sel)

        split_sel = QSplitter(Qt.Horizontal)

        # Banco de baterías
        self.grp_sel_bank = QGroupBox("Selección Banco de Baterías")
        v_sb = QVBoxLayout(self.grp_sel_bank)
        self.tbl_sel_bank = QTableWidget()
        self.tbl_sel_bank.setColumnCount(2)
        self.tbl_sel_bank.setHorizontalHeaderLabels(["Parámetro", "Valor"])
        configure_table_autoresize(self.tbl_sel_bank)
        self.tbl_sel_bank.verticalHeader().setVisible(False)
        self.btn_cap_tbl_sel_bank = QPushButton("Guardar captura de tabla")
        self.btn_cap_tbl_sel_bank.clicked.connect(lambda: self._save_widget_screenshot(self.tbl_sel_bank, "tabla_seleccion_banco"))
        v_sb.addWidget(self.btn_cap_tbl_sel_bank)
        v_sb.addWidget(self.tbl_sel_bank)

        self.grp_battery_selected = QGroupBox("Batería seleccionada")
        battery_row = QHBoxLayout(self.grp_battery_selected)
        battery_row.addWidget(QLabel("Marca"))
        self.cmb_battery_brand = QComboBox()
        battery_row.addWidget(self.cmb_battery_brand, 1)
        battery_row.addWidget(QLabel("Modelo"))
        self.cmb_battery_model = QComboBox()
        battery_row.addWidget(self.cmb_battery_model, 1)
        battery_row.addWidget(QLabel("Ah"))
        self.lbl_battery_ah = QLabel("—")
        battery_row.addWidget(self.lbl_battery_ah)
        self.btn_apply_battery = QPushButton("Aplicar selección")
        battery_row.addWidget(self.btn_apply_battery)
        v_sb.addWidget(self.grp_battery_selected)

        self.lbl_battery_warning = QLabel("")
        self.lbl_battery_warning.setWordWrap(True)
        self.lbl_battery_warning.setVisible(False)
        self.lbl_battery_warning.setStyleSheet(
            "QLabel {"
            "background: #FFF4CE;"
            "color: #5C3B00;"
            "border: 1px solid #F0C36D;"
            "border-radius: 6px;"
            "padding: 6px 8px;"
            "}"
        )
        v_sb.addWidget(self.lbl_battery_warning)

        # Cargador de baterías
        self.grp_sel_charger = QGroupBox("Selección Cargador de Baterías")
        v_sc = QVBoxLayout(self.grp_sel_charger)
        self.tbl_sel_charger = QTableWidget()
        self.tbl_sel_charger.setColumnCount(2)
        self.tbl_sel_charger.setHorizontalHeaderLabels(["Parámetro", "Valor"])
        configure_table_autoresize(self.tbl_sel_charger)
        self.tbl_sel_charger.verticalHeader().setVisible(False)
        self.btn_cap_tbl_sel_charger = QPushButton("Guardar captura de tabla")
        self.btn_cap_tbl_sel_charger.clicked.connect(lambda: self._save_widget_screenshot(self.tbl_sel_charger, "tabla_seleccion_cargador"))
        v_sc.addWidget(self.btn_cap_tbl_sel_charger)
        v_sc.addWidget(self.tbl_sel_charger)

        split_sel.addWidget(self.grp_sel_bank)
        split_sel.addWidget(self.grp_sel_charger)
        split_sel.setStretchFactor(0, 1)
        split_sel.setStretchFactor(1, 1)

        btns = QHBoxLayout()
        self.btn_export_all = QPushButton("Exportar todo (un clic)")
        # Edición directa en tablas de selección
        self.tbl_sel_charger.itemChanged.connect(self._on_sel_charger_item_changed)
        self.tbl_sel_charger.cellDoubleClicked.connect(lambda r,c: self._edit_selection_cell(self.tbl_sel_charger, r, c))
        btns.addWidget(self.btn_export_all)
        btns.addStretch()
        page_sel_layout.addLayout(btns)

        page_sel_layout.addWidget(split_sel)
        self.inner_tabs.addTab(page_sel, "Selección")

        # ---- TAB 5: Resumen equipos ----
        page_sum = QWidget()
        page_sum_layout = QVBoxLayout(page_sum)

        self.grp_summary = QGroupBox("Resumen de equipos")
        v_sum = QVBoxLayout(self.grp_summary)

        self.tbl_summary = QTableWidget()
        self.tbl_summary.setColumnCount(4)
        self.tbl_summary.setHorizontalHeaderLabels([
            "Equipo",
            "TAG",
            "Capacidad calculada",
            "Capacidad comercial recomendada"
        ])
        configure_table_autoresize(self.tbl_summary)
        self.tbl_summary.verticalHeader().setVisible(False)

        self.btn_cap_tbl_summary = QPushButton("Guardar captura de tabla")
        self.btn_cap_tbl_summary.clicked.connect(lambda: self._save_widget_screenshot(self.tbl_summary, "tabla_resumen_equipos"))
        v_sum.addWidget(self.btn_cap_tbl_summary)
        v_sum.addWidget(self.tbl_summary)
        page_sum_layout.addWidget(self.grp_summary)

        self.inner_tabs.addTab(page_sum, "Resumen")

        self.setLayout(main_layout)

    def _connect_signals(self):
        self.tbl_datos.itemChanged.connect(self._on_datos_changed)
        self.tbl_comp.itemChanged.connect(self._on_comp_changed)
        self.tbl_cargas.itemChanged.connect(self._on_cargas_changed)
        self.tbl_ieee.itemChanged.connect(self._on_ieee_changed)
        if getattr(self, "cmb_vpc_mode", None) is not None:
            self.cmb_vpc_mode.currentTextChanged.connect(self._on_vpc_mode_changed)
        if getattr(self, "cmb_cells_mode", None) is not None:
            self.cmb_cells_mode.currentTextChanged.connect(self._on_cells_mode_changed)
        self.btn_add_from_scenario.clicked.connect(self._add_area_from_scenario)
        self.btn_del_area.clicked.connect(self._remove_selected_area)

        self.cmb_battery_brand.currentTextChanged.connect(self._on_battery_brand_changed)
        self.cmb_battery_model.currentTextChanged.connect(self._on_battery_model_changed)
        self.btn_apply_battery.clicked.connect(self._on_apply_battery_selected)
        self.btn_export_all.clicked.connect(self._export_all_one_click)

    # =================== helpers =========================
    def _invalidate_bc_bundle(self):
        self._bc_bundle = None
        self._ieee_last_result = None

    def _get_bc_bundle(self):
        """Return the latest Bank/Charger bundle, computing it if needed.

        Robust by design: optional services / refactors must NOT crash the UI at startup.
        """
        # 1) If we already have a recent bundle, use it
        bundle = getattr(self, "_bc_bundle", None)
        if bundle is not None:
            return bundle

        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        self._sync_bank_charger_factor_keys()
        periods = list(getattr(self, "_cycle_periods_cache", []) or [])
        rnd = getattr(self, "_cycle_random_cache", None)
        nominal_v = self._get_battery_nominal_v()
        available_battery_ah = self._materials_battery_capacities(nominal_v)
        selected_battery_ah = self._get_selected_battery_ah(nominal_v)

        # i_perm desde L1 (tabla permanentes)
        i_perm = 0.0
        try:
            r_l1 = self._row_index_of_code(CODE_L1)
        except Exception:
            r_l1 = -1

        if r_l1 >= 0:
            try:
                # In esta pantalla la columna de corriente es 'I [A]' (índice 3).
                # Históricamente se llamó tbl_cargas; si existiera tbl_perm lo usamos también.
                tbl = getattr(self, 'tbl_perm', None) or getattr(self, 'tbl_cargas', None)
                item = tbl.item(r_l1, 3) if tbl is not None else None
                val = item.text() if item is not None else ''
                i_perm = float(str(val).replace(',', '.')) if val not in ('', None) else 0.0
            except Exception:
                i_perm = 0.0

        self._last_engine_issues = []

        # 2) Preferred path: CalcService (if available)
        try:
            cs = getattr(self.data_model, "calc_service", None)
            if cs and hasattr(cs, "recalc_bank_charger"):
                cs.recalc_bank_charger(
                    periods=periods,
                    rnd=rnd,
                    i_perm=float(i_perm or 0.0),
                    available_battery_ah=available_battery_ah,
                    selected_battery_ah=selected_battery_ah,
                )
                bundle = getattr(cs, "runtime_cache", {}).get("bank_charger_bundle")
                if bundle is not None:
                    self._bc_bundle = bundle
                    return bundle
        except Exception:
            logging.getLogger(__name__).debug("CalcService bank_charger failed", exc_info=True)

        # 3) Fallback: legacy SSAAEngine
        bundle = None
        try:
            from services.ssaa_engine import SSAAEngine
            res = SSAAEngine().compute_bank_charger(
                proyecto=proyecto,
                periods=periods,
                rnd=rnd,
                i_perm=float(i_perm or 0.0),
                available_battery_ah=available_battery_ah,
                selected_battery_ah=selected_battery_ah,
            )
            self._last_engine_issues = list((getattr(res, "issues", None) or []))
            bundle = getattr(res, "bank_charger", None)
        except Exception:
            logging.getLogger(__name__).debug("Legacy SSAAEngine bank_charger failed", exc_info=True)
            bundle = None

        # 4) If engine could not produce a bundle, return an empty compatible bundle
        if bundle is None:
            from domain.bank_charger_engine import BankChargerBundle
            bundle = BankChargerBundle(
                ieee=None,
                missing_kt_keys=[],
                bank=None,
                charger=None,
                ah_commercial_str="—",
                i_charger_commercial_str="—",
                warnings=[getattr(i, "message", str(i)) for i in (self._last_engine_issues or [])],
            )

        self._bc_bundle = bundle
        return bundle

    def _ieee_missing_kt_report(self):
        periods = list(self._cycle_periods_cache) if self._cycle_periods_cache else []
        if not periods:
            return {"missing": True, "details": ["No hay ciclo de trabajo."]}

        store = self._get_ieee_kt_store()
        n = len(periods)
        missing_keys = []
        for s in range(1, n+1):
            for i in range(1, s+1):
                key = f"S{s}_P{i}"
                val = store.get(key, "")
                try:
                    _ = float(str(val).replace(",", ".")) if val not in ("", None) else None
                except Exception:
                    _ = None
                if _ is None:
                    missing_keys.append(key)
        return {"missing": bool(missing_keys), "details": missing_keys}

    def _set_table_value_or_widget(self, table, row, col, text):
        w = table.cellWidget(row, col)
        if w is not None:
            if isinstance(w, QComboBox):
                idx = w.findText(str(text))
                if idx >= 0:
                    w.blockSignals(True)
                    w.setCurrentIndex(idx)
                    w.blockSignals(False)
            return
        self._set_cell(table, row, col, text, editable=False)

    def _load_modes_from_project(self) -> None:
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        vpc_mode = str(proyecto.get("vpc_final_mode", "auto") or "auto").strip().lower()
        cells_mode = str(proyecto.get("num_celdas_mode", "auto") or "auto").strip().lower()

        if getattr(self, "cmb_vpc_mode", None) is not None:
            self.cmb_vpc_mode.blockSignals(True)
            self.cmb_vpc_mode.setCurrentIndex(0 if vpc_mode != "manual" else 1)
            self.cmb_vpc_mode.blockSignals(False)
        if getattr(self, "cmb_cells_mode", None) is not None:
            self.cmb_cells_mode.blockSignals(True)
            self.cmb_cells_mode.setCurrentIndex(0 if cells_mode != "manual" else 1)
            self.cmb_cells_mode.blockSignals(False)

    def _get_vpc_mode(self) -> str:
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        if getattr(self, "cmb_vpc_mode", None) is not None:
            mode = str(self.cmb_vpc_mode.currentText() or "").strip().lower()
            return "manual" if mode == "manual" else "auto"
        return str(proyecto.get("vpc_final_mode", "auto") or "auto").strip().lower()

    def _get_cells_mode(self) -> str:
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        if getattr(self, "cmb_cells_mode", None) is not None:
            mode = str(self.cmb_cells_mode.currentText() or "").strip().lower()
            return "manual" if mode == "manual" else "auto"
        return str(proyecto.get("num_celdas_mode", "auto") or "auto").strip().lower()

    def _on_vpc_mode_changed(self, text: str):
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        mode = "manual" if str(text or "").strip().lower() == "manual" else "auto"
        proyecto["vpc_final_mode"] = mode
        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)
        self._apply_combo_edit_style(getattr(self, "vcell_combo", None), editable=(mode == "manual"))
        self._refresh_datos_comp_derived()

    def _on_cells_mode_changed(self, text: str):
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        mode = "manual" if str(text or "").strip().lower() == "manual" else "auto"
        proyecto["num_celdas_mode"] = mode
        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)
        self._refresh_datos_comp_derived()

    def _vpc_list(self) -> list:
        vals = []
        if getattr(self, "vcell_combo", None) is None:
            return vals
        for i in range(self.vcell_combo.count()):
            txt = str(self.vcell_combo.itemText(i) or "").strip()
            try:
                vals.append(float(txt.replace(",", ".")))
            except Exception:
                continue
        vals = [v for v in vals if v > 0]
        vals.sort()
        return vals

    def _ceil_to_vpc_list(self, raw: float) -> float:
        vals = self._vpc_list()
        if not vals:
            return float(raw or 0.0)
        try:
            raw_v = float(raw or 0.0)
        except Exception:
            raw_v = 0.0
        for v in vals:
            if v >= raw_v:
                return v
        return vals[-1]

    def _apply_combo_edit_style(self, combo: QComboBox, editable: bool) -> None:
        if combo is None:
            return
        if editable:
            combo.setEnabled(True)
            combo.setStyleSheet(
                "QComboBox { background: #FFF9C4; }"
            )
        else:
            combo.setEnabled(False)
            combo.setStyleSheet(
                "QComboBox { background: transparent; }"
                "QComboBox:disabled { background: transparent; color: #000000; }"
                "QComboBox::drop-down:disabled { background: transparent; border: 0px; }"
            )

    def _read_float_from_combo_cell(self, table: QTableWidget, row: int, col: int) -> float:
        w = table.cellWidget(row, col)
        if isinstance(w, QComboBox):
            txt = (w.currentText() or "").strip().replace(",", ".")
            try:
                return float(txt)
            except Exception:
                return 0.0
        # fallback: item
        return self._read_float_cell(table, row, col)

    def _float_options_for_batt_nom(self, batt_nom: float):
        if batt_nom == 2:
            return ["2,25", "2,26", "2,27", "2,28", "2,29", "2,30"], "2,30"
        if batt_nom == 6:
            return [
                "6,80","6,81","6,82","6,83","6,84","6,85","6,86","6,87","6,88","6,89","6,90"
            ], "6,80"
        # 12V
        return ["13,5", "13,6", "13,7", "13,8"], "13,8"

    def _install_batt_nom_combo(self, row: int, col: int):
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        cb = QComboBox()
        cb.addItems(["2", "6", "12"])
        cb.setProperty("userField", True)
        # default 2
        cur = str(proyecto.get("bateria_tension_nominal", "2")).strip()
        if cur not in ("2", "6", "12"):
            cur = "2"
        cb.setCurrentText(cur)
        cb.currentTextChanged.connect(self._on_batt_nom_changed)
        self.tbl_datos.setCellWidget(row, col, cb)

    def _install_float_combo(self, row: int, col: int):
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        batt_nom = self._read_float_from_combo_cell(self.tbl_datos, 0, 1) or 2.0
        options, default = self._float_options_for_batt_nom(batt_nom)
        cb = QComboBox()
        cb.addItems(options)
        cb.setProperty("userField", True)
        # intentar mantener lo guardado
        cur = str(proyecto.get("tension_flotacion_celda", "")).strip().replace(".", ",")
        if cur and cur in options:
            cb.setCurrentText(cur)
        else:
            cb.setCurrentText(default)
        cb.currentTextChanged.connect(self._on_float_combo_changed)
        self.tbl_datos.setCellWidget(row, col, cb)

    def _on_batt_nom_changed(self, _text: str):
        if self._updating:
            return
        # Reinstalar combo de flotación según nominal
        self._updating = True
        try:
            # reemplazar widget en fila 1
            self._install_float_combo(row=1, col=1)
        finally:
            self._updating = False
        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)
        self.recalculate_all()
        self._refresh_battery_selector()

    def _on_float_combo_changed(self, _text: str):
        if self._updating:
            return
        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)
        self.recalculate_all()

    def _install_vcell_combo(self):
        """Combo de Vpc final seleccionada (usuario). Se instala en fila 6 (tabla datos)."""
        self.vcell_combo = QComboBox()
        self.vcell_combo.addItems([
            "1.60","1.63","1.65","1.67","1.70","1.73","1.75","1.77","1.80","1.83","1.85","1.87","1.90","1.93"
        ])
        self.vcell_combo.setProperty("userField", True)
        # fila 6 = "Tensión final por celda seleccionada"
        try:
            self.tbl_datos.setCellWidget(6, 1, self.vcell_combo)
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
        self.vcell_combo.currentTextChanged.connect(self._on_vcell_combo_changed)

        stored = self._proj_value("v_celda_sel_usuario")
        if stored:
            idx = self.vcell_combo.findText(str(stored))
            if idx >= 0:
                self.vcell_combo.blockSignals(True)
                self.vcell_combo.setCurrentIndex(idx)
                self.vcell_combo.blockSignals(False)

    def _export_all_one_click(self):
        items = [
            (self.tbl_datos, '01_datos_sistema'),
            (self.tbl_comp, '02_comprobacion'),
            (self.tbl_cargas, '03_perfil_cargas'),
            (self.tbl_cycle, '04_ciclo_trabajo'),
            (self.plot_widget, '05_grafico_ciclo'),
            (self.tbl_ieee, '06_ieee_485'),
            (self.tbl_sel_bank, '07_seleccion_banco'),
            (self.tbl_sel_charger, '08_seleccion_cargador'),
            (self.tbl_summary, '09_resumen'),
        ]
        export_all_one_click(self, items)

    def _save_widget_screenshot(self, widget: QWidget, base_name: str = 'captura'):
        save_widget_screenshot(self, widget, base_name)


    def _schedule_updates(self):
        return self._controller.schedule_updates()

    def _proj_value(self, key, *alts):
        p = getattr(self.data_model, "proyecto", {}) or {}
        if key in p:
            return p.get(key, "")
        for k in alts:
            if k in p:
                return p.get(k, "")
        return ""

    def _get_saved_perfil_cargas(self) -> list:
        pers = getattr(self, "persistence", None)
        if pers is None and hasattr(self, "_controller"):
            pers = getattr(self._controller, "persistence", None)
        if pers is None:
            return []
        return pers.get_saved_perfil_cargas() or []

    def _get_saved_random_loads(self) -> dict:
        pers = getattr(self, "persistence", None)
        if pers is None and hasattr(self, "_controller"):
            pers = getattr(self._controller, "persistence", None)
        if pers is None:
            return {}
        return pers.get_saved_random_loads() or {}

    @staticmethod
    def _count_saved_items(value) -> int:
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return len(value)
        return 0

    def _log_perfil_snapshot(self, reason: str) -> None:
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        cfg = proyecto.get("bank_charger", None)
        cfg_dict = cfg if isinstance(cfg, dict) else {}
        sig = (
            isinstance(cfg, dict),
            self._count_saved_items(proyecto.get("perfil_cargas")),
            self._count_saved_items(cfg_dict.get("perfil_cargas")),
            self._count_saved_items(proyecto.get("cargas_aleatorias")),
            self._count_saved_items(cfg_dict.get("cargas_aleatorias")),
        )
        if getattr(self, "_last_perfil_snapshot_sig", None) == sig:
            return
        self._last_perfil_snapshot_sig = sig
        logging.getLogger(__name__).info(
            "BankCharger %s snapshot has_bank_charger=%s perfil_root=%d perfil_bank=%d ale_root=%d ale_bank=%d",
            reason,
            sig[0],
            sig[1],
            sig[2],
            sig[3],
            sig[4],
        )

    def _norm_code(self, code: str) -> str:
        return (code or "").strip().upper()

    def _commit_any_table(self, table: QTableWidget):
        return self._controller.commit_any_table(table)

    def commit_pending_edits(self):
        return self._controller.commit_pending_edits()

    def _read_float_cell(self, table, row, col):
        item = table.item(row, col)
        if item is None:
            return 0.0
        text = item.text().replace(",", ".").strip()
        try:
            return float(text)
        except ValueError:
            return 0.0

    def _read_int_cell(self, table, row, col):
        item = table.item(row, col)
        if item is None:
            return 0
        text = item.text().strip()
        try:
            return int(text)
        except ValueError:
            return 0

    def _ensure_item(self, table: QTableWidget, r: int, c: int) -> QTableWidgetItem:
        it = table.item(r, c)
        if it is None:
            it = QTableWidgetItem("")
            table.setItem(r, c, it)
        return it

    def _set_span_with_placeholders(self, table: QTableWidget, r: int, c: int, rs: int, cs: int):
        table.setSpan(r, c, rs, cs)
        # placeholders en todo el span para evitar celdas huérfanas
        for rr in range(r, r + rs):
            for cc in range(c, c + cs):
                self._ensure_item(table, rr, cc)

    def _set_cell(self, table, row, col, value, editable=False):
        item = table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            table.setItem(row, col, item)
        item.setText(str(value))
        flags = item.flags()
        if editable:
            item.setFlags(flags | Qt.ItemIsEditable)
            # Resaltar campos modificables (amarillo tenue)
            item.setBackground(_theme_color("INPUT_EDIT_BG", "#FFF9C4"))
        else:
            item.setFlags(flags & ~Qt.ItemIsEditable)
            # limpiar background si venía de antes
            item.setBackground(QColor(0, 0, 0, 0))

    def _set_table_row_ro(self, table, row, values):
        for c, v in enumerate(values):
            it = QTableWidgetItem(str(v))
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, c, it)

    def _set_text_cell(self, table, row, col, text, editable=False):
        it = table.item(row, col)
        if it is None:
            it = QTableWidgetItem("")
            table.setItem(row, col, it)
        it.setText(str(text))
        if editable:
            it.setFlags(it.flags() | Qt.ItemIsEditable)
            it.setBackground(_theme_color("INPUT_EDIT_BG", "#FFF9C4"))
        else:
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            it.setBackground(QColor(0, 0, 0, 0))

    def _row_index_of_lal(self) -> int:
        for r in range(self.tbl_cargas.rowCount()):
            it = self.tbl_cargas.item(r, 0)
            if it and self._norm_code(it.text()) == self._norm_code(CODE_LAL):
                return r
        return -1

    # =================== callbacks =======================
    def _on_vcell_combo_changed(self, text: str):
        if self._updating:
            return -1
        text = (text or "").strip()
        proyecto = getattr(self.data_model, "proyecto", {}) or {}

        try:
            self._user_vcell_sel = float(text.replace(",", "."))
            proyecto["v_celda_sel_usuario"] = text
        except ValueError:
            self._user_vcell_sel = None
            proyecto["v_celda_sel_usuario"] = ""

        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)

        self.recalculate_all()

    def _on_datos_changed(self, item):
        if self._updating:
            return
        # En esta pestaña, los inputs del usuario son combos (fila 0 y 1) y
        # el número de celdas en Comprobación (tabla derecha). No usamos edición
        # directa en celdas de esta tabla.
        return

    def _on_comp_changed(self, item):
        if self._updating:
            return
        if item.column() != 1:
            return
        if item.row() != 0:
            return

        text = item.text().strip()
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        proyecto["num_celdas_usuario"] = text

        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)

        self.recalculate_all()

    def _on_cargas_changed(self, item):
        if self._updating:
            return
        # Centralized update pipeline (keeps sequencing consistent)
        try:
            self._controller.pipeline.on_profile_changed()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error en Perfil de cargas",
                f"Ocurrió un error al actualizar el perfil/ciclo/IEEE485.\n\n{e}",
            )

    def _on_ieee_changed(self, item):
        """Sólo permitimos editar Kt (col 5)."""
        if self._updating:
            return
        if item is None:
            return
        if item.column() != 5:
            return
        # Centralized update pipeline
        try:
            self._controller.pipeline.on_ieee_kt_changed()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error en IEEE 485",
                f"Ocurrió un error al actualizar la tabla IEEE 485 / selección / resumen.\n\n{e}",
            )

    # =================== cálculo principal ===============
    def recalculate_all(self):
        self._updating = True
        try:
            proyecto = getattr(self.data_model, "proyecto", {}) or {}

            # 1) Leer inputs desde UI
            # Row 0: nominal batería (2/6/12) vía combo
            batt_nom = self._read_float_from_combo_cell(self.tbl_datos, 0, 1)
            # Row 1: tensión de flotación (depende de nominal) vía combo
            v_cell_float = self._read_float_from_combo_cell(self.tbl_datos, 1, 1)

            # Número de celdas (usuario) puede venir con decimales (ej: 54.00)
            n_user_in = self._read_float_cell(self.tbl_comp, 0, 1)
            if not n_user_in:
                try:
                    n_user_in = float(str(proyecto.get("num_celdas_usuario", 0)).replace(",", "."))
                except Exception:
                    n_user_in = 0.0
            n_user = int(math.ceil(n_user_in)) if n_user_in > 0 else 0

            # 2) Persistir inputs en proyecto (fuente de verdad)
            if batt_nom and batt_nom > 0:
                proyecto["bateria_tension_nominal"] = batt_nom
            if v_cell_float and v_cell_float > 0:
                proyecto["tension_flotacion_celda"] = v_cell_float
            if n_user > 0:
                proyecto["num_celdas_usuario"] = n_user
            else:
                proyecto["num_celdas_usuario"] = ""

            # 3) Cálculo único (service via controller)
            res = self._controller.run_battery_sizing(proyecto)
            # 5) Elegir Vpc seleccionada: usuario > cálculo
            # (tu domain aún no calcula "v_cell_sel", así que dejamos la combo como "selección visual")
            v_cell_sel = self._user_vcell_sel  # puede ser None
            vpc_mode = self._get_vpc_mode()
            cells_mode = self._get_cells_mode()

            def fnum(x, nd=2):
                try:
                    return round(float(x), nd)
                except Exception:
                    return ""

            # 6) Pintar TABLA DATOS
            # Row 0 y 1 son combos (se actualizan con _set_table_value_or_widget)
            self._set_table_value_or_widget(self.tbl_datos, 0, 1, fnum(batt_nom, 0) if batt_nom else "")
            self._set_table_value_or_widget(self.tbl_datos, 1, 1, fnum(res.v_cell_float, 2) if res.v_cell_float is not None else "")

            # Sistema
            self._set_cell(self.tbl_datos, 2, 1, fnum(res.v_nominal, 2) if res.v_nominal is not None else "", editable=False)
            self._set_cell(self.tbl_datos, 3, 1, fnum(res.v_max, 2) if res.v_max is not None else "", editable=False)
            self._set_cell(self.tbl_datos, 4, 1, fnum(res.v_min, 2) if res.v_min is not None else "", editable=False)

            # (1.3) Número de celdas (Datos del Sistema) = Vmax / Vfloat (2 dec)
            n_cells_sys = ""
            try:
                if res.v_max is not None and res.v_cell_float:
                    n_cells_sys = float(res.v_max) / float(res.v_cell_float)
            except Exception:
                n_cells_sys = ""

            # (1.4) Número de celdas (Comprobación) = ceil(N sys).
            n_req = int(math.ceil(float(n_cells_sys))) if n_cells_sys != "" else 0
            n_user_in = self._read_float_cell(self.tbl_comp, 0, 1)
            if cells_mode != "manual":
                n_user = int(n_req) if n_req > 0 else 0
            else:
                if n_user_in and n_user_in > 0:
                    n_user = int(math.ceil(float(n_user_in)))
                else:
                    n_user = int(n_req) if n_req > 0 else 0

            # Pintar N sys en tabla datos (fila 7)
            self._set_cell(self.tbl_datos, 7, 1, fnum(n_cells_sys, 2) if n_cells_sys != "" else "", editable=False)

            # (1.5) Tensión final por celda calculada = Vmin / N_user (ceil a lista)
            v_cell_min_raw = ""
            try:
                if res.v_min is not None and n_user:
                    v_cell_min_raw = float(res.v_min) / float(n_user)
            except Exception:
                v_cell_min_raw = ""

            v_cell_min_calc = self._ceil_to_vpc_list(v_cell_min_raw) if v_cell_min_raw != "" else ""
            self._set_cell(self.tbl_datos, 5, 1, fnum(v_cell_min_calc, 2) if v_cell_min_calc != "" else "", editable=False)

            # “Seleccionada” = combo (si existe)
            if vpc_mode != "manual" and v_cell_min_calc != "":
                self._set_table_value_or_widget(self.tbl_datos, 6, 1, fnum(v_cell_min_calc, 2))
                proyecto["v_celda_sel_usuario"] = fnum(v_cell_min_calc, 2)
                v_cell_sel = v_cell_min_calc
            else:
                self._set_table_value_or_widget(self.tbl_datos, 6, 1, fnum(v_cell_sel, 2) if v_cell_sel is not None else "")

            self._apply_combo_edit_style(getattr(self, "vcell_combo", None), editable=(vpc_mode == "manual"))

            # 7) Pintar TABLA COMPROBACIÓN (user)
            self._set_cell(self.tbl_comp, 0, 1, f"{int(n_user):d}" if n_user else "", editable=(cells_mode == "manual"))

            comp_vmax = ""
            comp_vmin = ""
            try:
                if n_user and res.v_cell_float:
                    comp_vmax = float(n_user) * float(res.v_cell_float)
            except Exception:
                comp_vmax = ""
            try:
                if n_user and v_cell_sel is not None:
                    comp_vmin = float(n_user) * float(v_cell_sel)
            except Exception:
                comp_vmin = ""

            self._set_cell(self.tbl_comp, 1, 1, fnum(comp_vmax, 2) if comp_vmax != "" else "", editable=False)
            self._set_cell(self.tbl_comp, 2, 1, fnum(comp_vmin, 2) if comp_vmin != "" else "", editable=False)

            # Warnings for manual modes
            try:
                if cells_mode == "manual" and n_req > 0 and n_user < n_req:
                    QMessageBox.warning(
                        self,
                        "Comprobación",
                        f"El número de celdas es menor al mínimo recomendado ({n_req}).",
                    )
                if vpc_mode == "manual" and v_cell_min_calc != "" and v_cell_sel is not None:
                    if float(v_cell_sel) < float(v_cell_min_calc):
                        QMessageBox.warning(
                            self,
                            "Vpc seleccionada",
                            "La Vpc seleccionada es menor al mínimo recomendado.",
                        )
            except Exception:
                pass

            # 8) Si hay errores del domain, mostrarlos (sin cerrar app)
            if not res.ok:
                # Muestra el primer error (o arma resumen si quieres)
                errs = [i for i in res.issues if i.level == "error"]
                if errs:
                    # Do not show modal warnings during automatic refresh.
                    # Keep issues for panels/tables to display.
                    self._last_engine_issues = list(errs)
        finally:
            self._updating = False

            # resto igual
            self._refresh_perfil_autocalc()
            self._update_cycle_table()
            self._update_ieee485_table()
            self._update_selection_tables()
            self._update_summary_table()
            self._schedule_updates()

    # ================== estructura inicial =================
    def _fill_datos_sistema(self):
        self.tbl_datos.setRowCount(0)

        # Nota:
        # - "Tensión nominal [V]" acá corresponde a la UNIDAD/CELDA de batería (2V/6V/12V)
        # - "Tensión nominal sistema [V]" corresponde a la tensión DC del tablero (p.ej. 110 V)
        batt_nom = self._proj_value("bateria_tension_nominal")
        v_float = self._proj_value("tension_flotacion_celda")
        v_nom = self._proj_value("tension_nominal")
        v_max_pct = self._proj_value("max_voltaje_cc")
        v_min_pct = self._proj_value("min_voltaje_cc")
        v_max_val = self._proj_value("v_max")
        v_min_val = self._proj_value("v_min")

        rows = [
            ("Tensión Nominal [V]", batt_nom),
            ("Tensión de carga en flotación [V]", v_float),
            ("Tensión nominal sistema [V]", v_nom),
            (f"Tensión máxima (+{v_max_pct} %) [V]", f"{float(v_max_val):.2f}" if v_max_val not in (None, "", "—") else ""),
            (f"Tensión mínima (-{v_min_pct} %) [V]", v_min_val),
            ("Tensión final por celda calculada [Vpc]", "—"),
            ("Tensión final por celda seleccionada [Vpc]", "—"),
            ("Número de celdas", "—"),
        ]

        self.tbl_datos.setRowCount(len(rows))
        for r, (label, value) in enumerate(rows):
            self._set_table_row_ro(self.tbl_datos, r, [label, value])

        # --- Widgets (combos) ---
        # Row 0: batt nominal
        self._install_batt_nom_combo(row=0, col=1)
        # Row 1: float voltage (depende de nominal)
        self._install_float_combo(row=1, col=1)
        self.tbl_datos.resizeRowsToContents()

    def _fill_comprobacion(self):
        self.tbl_comp.setRowCount(0)
        rows = [
            ("Número de celdas", "—"),
            ("Tensión máxima [V]", "—"),
            ("Tensión mínima [V]", "—"),
        ]
        self.tbl_comp.setRowCount(len(rows))
        for r, (label, value) in enumerate(rows):
            self._set_table_row_ro(self.tbl_comp, r, [label, value])
        self.tbl_comp.resizeRowsToContents()

    def _refresh_datos_comp_derived(self) -> None:
        """Render derived values without running engine calculations."""
        if getattr(self, "_updating", False):
            return

        def _to_float(val) -> float:
            try:
                return float(str(val).replace(",", "."))
            except Exception:
                return 0.0

        def _cell_text(table, r, c) -> str:
            it = table.item(r, c)
            return it.text().strip() if it else ""

        proyecto = getattr(self.data_model, "proyecto", {}) or {}

        v_float = _to_float(proyecto.get("tension_flotacion_celda", ""))
        v_max = _to_float(proyecto.get("v_max", "")) or _to_float(_cell_text(self.tbl_datos, 3, 1))
        v_min = _to_float(proyecto.get("v_min", "")) or _to_float(_cell_text(self.tbl_datos, 4, 1))

        n_user = _to_float(proyecto.get("num_celdas_usuario", "")) or _to_float(_cell_text(self.tbl_comp, 0, 1))
        n_cells = int(math.ceil(n_user)) if n_user > 0 else 0

        v_sel = self._user_vcell_sel
        if not v_sel:
            v_sel = _to_float(proyecto.get("v_celda_sel_usuario", "")) or _to_float(_cell_text(self.tbl_datos, 6, 1))

        n_sys = (v_max / v_float) if (v_max > 0 and v_float > 0) else 0.0
        n_req = int(math.ceil(n_sys)) if n_sys > 0 else 0
        cells_mode = self._get_cells_mode()
        if cells_mode != "manual":
            n_cells = n_req
            if n_cells > 0:
                proyecto["num_celdas_usuario"] = n_cells

        vpc_min_raw = (v_min / n_cells) if (v_min > 0 and n_cells > 0) else 0.0
        vpc_min_calc = self._ceil_to_vpc_list(vpc_min_raw) if vpc_min_raw > 0 else 0.0
        vpc_mode = self._get_vpc_mode()
        if vpc_mode != "manual" and vpc_min_calc > 0:
            v_sel = vpc_min_calc
            proyecto["v_celda_sel_usuario"] = f"{v_sel:.2f}"

        comp_vmax = (n_cells * v_float) if (n_cells > 0 and v_float > 0) else 0.0
        comp_vmin = (n_cells * v_sel) if (n_cells > 0 and v_sel > 0) else 0.0

        self._updating = True
        try:
            self.tbl_datos.blockSignals(True)
            self.tbl_comp.blockSignals(True)

            self._set_text_cell(self.tbl_datos, 5, 1, f"{vpc_min_calc:.2f}" if vpc_min_calc > 0 else "—", editable=False)
            if v_sel and v_sel > 0:
                self._set_table_value_or_widget(self.tbl_datos, 6, 1, f"{v_sel:.2f}")
            else:
                self._set_text_cell(self.tbl_datos, 6, 1, "—", editable=False)
            self._set_text_cell(self.tbl_datos, 7, 1, f"{n_sys:.2f}" if n_sys > 0 else "—", editable=False)

            self._set_text_cell(self.tbl_comp, 0, 1, f"{n_cells:d}" if n_cells > 0 else "—", editable=(cells_mode == "manual"))
            self._set_text_cell(self.tbl_comp, 1, 1, f"{comp_vmax:.2f}" if comp_vmax > 0 else "—", editable=False)
            self._set_text_cell(self.tbl_comp, 2, 1, f"{comp_vmin:.2f}" if comp_vmin > 0 else "—", editable=False)
        finally:
            self.tbl_comp.blockSignals(False)
            self.tbl_datos.blockSignals(False)
            self._updating = False

    # ===================== Vmin / Autonomía ======================
    def _get_vmin_cc(self) -> float:
        p = getattr(self.data_model, "proyecto", {}) or {}

        # Preferimos recalcular desde tensión_nominal y min_voltaje_cc si existen,
        # para no quedar “pegados” a un v_min antiguo.
        try:
            v_nom = float(p.get("tension_nominal", "") or 0)
        except Exception:
            v_nom = 0.0

        try:
            min_pct = float(p.get("min_voltaje_cc", "") or 0)
        except Exception:
            min_pct = 0.0

        if v_nom > 0 and min_pct > 0:
            return v_nom * (1.0 - min_pct / 100.0)

        try:
            v_min = float(p.get("v_min", "") or 0)
            if v_min > 0:
                return v_min
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        # Fallbacks
        if v_nom <= 0:
            try:
                v_nom = float(p.get("v_nom", "") or 0)
            except Exception:
                v_nom = 0.0

        if v_nom > 0:
            return v_nom

        return 0.0

    def _get_autonomia_min(self) -> float:
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        try:
            t_aut_h = float(proyecto.get("tiempo_autonomia", "") or 0.0)
        except Exception:
            t_aut_h = 0.0
        return (t_aut_h * 60.0) if t_aut_h > 0 else 0.0

    def _get_model_gabinetes(self):
        return cc_get_model_gabinetes(self.data_model)

    def _compute_cc_profile_totals(self):
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        gabinetes = self._get_model_gabinetes()
        return compute_cc_profile_totals(proyecto=proyecto, gabinetes=gabinetes)

    # ================== Perfil de Cargas ==================
    def _compute_momentary_scenarios(self):
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        gabinetes = self._get_model_gabinetes()

        vmin = self._get_vmin_cc()
        if vmin <= 0:
            vmin = 1.0

        escenarios = compute_momentary_scenarios(proyecto=proyecto, gabinetes=gabinetes, vmin=vmin)
        if not isinstance(escenarios, dict):
            return {}

        # Prefer computed tail-from-permanents cache when available.
        cached_tail = None
        calc = proyecto.get("calculated", None)
        if isinstance(calc, dict):
            cc_calc = calc.get("cc", None)
            if isinstance(cc_calc, dict):
                summary = cc_calc.get("summary", None)
                if isinstance(summary, dict):
                    raw_tail = summary.get("p_mom_perm", None)
                    try:
                        cached_tail = float(raw_tail)
                    except Exception:
                        cached_tail = None

        if cached_tail is None:
            return escenarios

        try:
            computed_tail = float(compute_momentary_from_permanents(proyecto, gabinetes) or 0.0)
        except Exception:
            computed_tail = 0.0
        delta_tail = float(cached_tail - computed_tail)
        if abs(delta_tail) < 1e-9:
            return escenarios

        scn1 = escenarios.get(1, escenarios.get("1", None))
        if not isinstance(scn1, dict):
            scn1 = {"p_total": 0.0, "i_total": 0.0}
        p_total = max(0.0, float(scn1.get("p_total", 0.0) or 0.0) + delta_tail)
        scn1["p_total"] = float(p_total)
        scn1["i_total"] = float(p_total / float(vmin))
        escenarios[1] = scn1
        return escenarios

    def _extract_scenario_id(self, desc: str) -> int | None:
        text = (desc or "").strip()
        if not text:
            return None
        match = re.search(r"Escenario\\s+(\\d+)", text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except Exception:
            return None

    def _get_used_scenario_ids(self) -> set[int]:
        used: set[int] = set()
        for r in range(self.tbl_cargas.rowCount()):
            it_desc = self.tbl_cargas.item(r, 1)
            if it_desc is None:
                continue
            sid = it_desc.data(Qt.UserRole)
            if isinstance(sid, int):
                used.add(sid)
                continue
            if isinstance(sid, str) and sid.isdigit():
                used.add(int(sid))
                continue
            parsed = self._extract_scenario_id(it_desc.text() if it_desc else "")
            if parsed is not None:
                used.add(parsed)
        return used

    def _load_perfil_cargas_from_model(self):
        return self._controller.profile_presenter.load_from_model()

    def _fill_perfil_cargas(self, save_to_model: bool = True):
        return self._controller.profile_presenter.fill_defaults(save_to_model=save_to_model)

    def _apply_perfil_editability(self):
        return self._controller.profile_presenter.apply_editability()

    def _row_index_of_code(self, code: str) -> int:
        return self._controller.profile_presenter.row_index_of_code(code)

    def _refresh_perfil_autocalc(self):
        return self._controller.profile_presenter.refresh_autocalc()

    def _save_perfil_cargas_to_model(self):
        return self._controller.save_perfil_cargas_to_model()

    def _finalize_profile_programmatic_change(self):
        """Persist + refresh dependencias tras mutaciones programáticas de tbl_cargas."""
        try:
            self._controller.pipeline.on_profile_changed()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error en Perfil de cargas",
                f"Ocurrió un error al persistir/actualizar el Perfil de cargas.\n\n{e}",
            )

    def _next_load_id(self) -> str:
        existing_nums = set()
        for r in range(self.tbl_cargas.rowCount()):
            it = self.tbl_cargas.item(r, 0)
            if not it:
                continue
            code = it.text().strip()
            cn = self._norm_code(code)
            if cn in (self._norm_code(CODE_L1), self._norm_code(CODE_LAL)):
                continue
            if cn.startswith("L") and cn[1:].isdigit():
                existing_nums.add(int(cn[1:]))

        n = 2
        while n in existing_nums or n == 1:
            n += 1
        return f"L{n}"
    def _remove_selected_area(self):
        row = self.tbl_cargas.currentRow()
        if row < 0:
            return

        it = self.tbl_cargas.item(row, 0)
        code = it.text().strip() if it else ""
        cn = self._norm_code(code)

        if cn == self._norm_code(CODE_L1):
            QMessageBox.warning(self, "No permitido", "La carga L1 no se puede eliminar.")
            return
        if cn == self._norm_code(CODE_LAL):
            QMessageBox.warning(self, "No permitido", "La carga L(al) no se puede eliminar.")
            return

        self._updating = True
        try:
            self.tbl_cargas.removeRow(row)
        finally:
            self._updating = False

        self._finalize_profile_programmatic_change()

    def _add_area_from_scenario(self):
        self.commit_pending_edits()
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        descs = proyecto.get("cc_escenarios", {}) or {}

        escenarios = self._compute_momentary_scenarios()
        if not escenarios:
            QMessageBox.information(self, "Escenarios C.C.",
                                    "No hay escenarios momentáneos con datos.\n"
                                    "Revisa Consumos C.C. (Momentáneos) y marca 'Incluir'.")
            return
        used_ids = self._get_used_scenario_ids()

        opciones = []
        for esc in sorted(escenarios.keys()):
            if int(esc) in used_ids:
                continue
            data = escenarios[esc]
            p = float(data.get("p_total", 0.0))
            i = float(data.get("i_total", 0.0))
            d = descs.get(str(esc), "")
            label = f"Escenario {esc} – {d} (P={p:.1f} W, I={i:.2f} A)"
            opciones.append((label, esc, p, i, d))

        if not opciones:
            QMessageBox.information(
                self,
                "No hay escenarios disponibles",
                "Ya fueron usados todos los escenarios de C.C. en el Perfil de cargas.",
            )
            return

        labels = [o[0] for o in opciones]
        sel_label, ok = QInputDialog.getItem(
            self, "Seleccionar escenario",
            "Escenario de C.C. para esta carga:",
            labels, 0, False
        )
        if not ok or not sel_label:
            return

        sel = None
        for label, esc, p_tot, i_tot, d in opciones:
            if label == sel_label:
                sel = (esc, p_tot, i_tot, d)
                break
        if sel is None:
            return
        esc_num, p_tot, i_tot, desc = sel
        if int(esc_num) in self._get_used_scenario_ids():
            QMessageBox.warning(
                self,
                "Escenario no disponible",
                "Ese escenario ya fue agregado al Perfil de cargas.",
            )
            return

        row_lal = self._row_index_of_lal()
        row = row_lal if row_lal >= 0 else self.tbl_cargas.rowCount()

        self._updating = True
        try:
            self.tbl_cargas.insertRow(row)
            code = self._next_load_id()

            # Propuesta inicial de tiempos: al final de la autonomía (1 min)
            t_aut = self._get_autonomia_min()
            t0_def = max(0.0, float(t_aut) - 1.0) if (t_aut and float(t_aut) > 0) else None
            dur_def = 1.0 if t0_def is not None else None

            valores = [
                code,
                f"Escenario {esc_num} – {desc}",
                f"{p_tot:.2f}",
                f"{i_tot:.2f}",
                (f"{t0_def:.0f}" if t0_def is not None else "—"),
                (f"{dur_def:.0f}" if dur_def is not None else "—"),
            ]
            for c, v in enumerate(valores):
                self.tbl_cargas.setItem(row, c, QTableWidgetItem(str(v)))
            it_desc = self.tbl_cargas.item(row, 1)
            if it_desc is not None:
                it_desc.setData(Qt.UserRole, int(esc_num))
        finally:
            self._updating = False

        self._apply_perfil_editability()
        self._finalize_profile_programmatic_change()

    # ===================== Tabla Ciclo de trabajo =====================
    def _extract_segments(self):
        def to_float(text):
            s = (text or "").strip()
            if not s or s == "—":
                return None
            s = s.replace(",", ".")
            try:
                return float(s)
            except ValueError:
                return None

        t_aut = self._get_autonomia_min()

        det = []
        rnd = None

        for r in range(self.tbl_cargas.rowCount()):
            code = self.tbl_cargas.item(r, 0).text().strip() if self.tbl_cargas.item(r, 0) else ""
            cn = self._norm_code(code)
            I = to_float(self.tbl_cargas.item(r, 3).text() if self.tbl_cargas.item(r, 3) else "")
            if I is None or I <= 0:
                continue

            if cn == self._norm_code(CODE_L1):
                t0 = 0.0
                dur = t_aut if t_aut > 0 else None
            else:
                t0 = to_float(self.tbl_cargas.item(r, 4).text() if self.tbl_cargas.item(r, 4) else "")
                dur = to_float(self.tbl_cargas.item(r, 5).text() if self.tbl_cargas.item(r, 5) else "")

            if t0 is None or dur is None or dur <= 0:
                continue
            t1 = t0 + dur

            if cn == self._norm_code(CODE_LAL):
                rnd = {"code": CODE_LAL, "I": I, "t0": t0, "t1": t1, "dur": dur}
            else:
                det.append({"code": code, "I": I, "t0": t0, "t1": t1, "dur": dur})

        return det, rnd

    def _update_cycle_table(self):
        return self._controller.update_cycle_table()

    def _cycle_sort_key(self, code: str):
        cn = self._norm_code(code)
        if cn == self._norm_code(CODE_L1):
            return (0, 0)
        if cn == self._norm_code(CODE_LAL):
            return (2, 0)
        if cn.startswith("L") and cn[1:].isdigit():
            return (1, int(cn[1:]))
        return (1, 9999)

    # ===================== Gráfico =====================
    def _update_profile_chart(self):
        if getattr(self, "inner_tabs", None) is not None and self.inner_tabs.currentIndex() != 1:
            return None
        return self._controller.update_profile_chart()

    def _schedule_active_inner_tab_refresh(self) -> None:
        tabs = getattr(self, "inner_tabs", None)
        if tabs is None:
            return
        if getattr(self, "_pending_inner_tab_refresh", False):
            return
        self._pending_inner_tab_refresh = True

        def _run_refresh():
            self._pending_inner_tab_refresh = False
            tabs_now = getattr(self, "inner_tabs", None)
            if tabs_now is None:
                return
            self._on_inner_tab_changed(tabs_now.currentIndex())

        QTimer.singleShot(0, _run_refresh)

    def _on_inner_tab_changed(self, idx: int):
        if getattr(self, "_updating", False):
            return
        try:
            self._controller.refresh_bank_charger_inner_tab(idx)
        except Exception:
            import logging
            logging.getLogger(__name__).debug("inner tab refresh failed", exc_info=True)

    def _build_ieee485_table_structure(self):
        return self._controller.build_ieee485_table_structure()

    def _get_ieee_kt_store(self):
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        store = proyecto.get("ieee485_kt", None)
        if not isinstance(store, dict):
            store = {}
            proyecto["ieee485_kt"] = store
        return store

    def _persist_ieee_kt_to_model(self):
        return self._controller.persist_ieee_kt_to_model()

    def _kt_for_key(self, key: str, default=""):
        store = self._get_ieee_kt_store()
        val = store.get(str(key), default)
        return val

    def _set_ro_cell(self, r, c, text, role_key=None):
        it = QTableWidgetItem("" if text is None else str(text))
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        if role_key is not None:
            it.setData(Qt.UserRole, role_key)
        self.tbl_ieee.setItem(r, c, it)

    def _set_kt_cell(self, r, key: str, value):
        it = QTableWidgetItem("" if value in (None, "") else str(value))
        it.setFlags((it.flags() | Qt.ItemIsEditable))
        it.setData(Qt.UserRole, key)  # redundante
        self.tbl_ieee.setItem(r, 5, it)

    def _set_section_header_row(self, r, text):
        self._set_span_with_placeholders(self.tbl_ieee, r, 0, 1, self.tbl_ieee.columnCount())
        it = self.tbl_ieee.item(r, 0)  # ya existe por placeholder
        it.setText(text)
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        font = it.font()
        font.setBold(True)
        it.setFont(font)

    def _update_ieee485_table(self):
        return self._controller.update_ieee485_table()

    def _get_bc_overrides(self) -> dict:
        proyecto = self.data_model.proyecto or {}
        ov = proyecto.get("bc_overrides", {})
        return ov if isinstance(ov, dict) else {}

    def _set_bc_overrides(self, ov: dict) -> None:
        proyecto = self.data_model.proyecto or {}
        proyecto["bc_overrides"] = ov
        self.data_model.mark_dirty(True)

    @staticmethod
    def _as_float(value):
        try:
            return float(str(value).replace(",", "."))
        except Exception:
            return None

    def _bank_charger_cfg(self) -> dict:
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        cfg = proyecto.get("bank_charger", {})
        if not isinstance(cfg, dict):
            cfg = {}
            proyecto["bank_charger"] = cfg
        return cfg

    def _sync_bank_charger_factor_keys(self) -> None:
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        cfg = self._bank_charger_cfg()
        mappings = (
            ("k1_margen", "bb_margen_diseno", 1.15),
            ("k2_altitud", "bb_k2_temp", 1.0),
            ("k3_envejecimiento", "bb_factor_envejec", 1.25),
        )
        for cfg_key, legacy_key, default in mappings:
            cfg_val = self._as_float(cfg.get(cfg_key, None))
            if cfg_val is not None and cfg_val > 0:
                proyecto[legacy_key] = cfg_val
                continue
            legacy_val = self._as_float(proyecto.get(legacy_key, default))
            if legacy_val is None or legacy_val <= 0:
                legacy_val = float(default)
            proyecto[legacy_key] = legacy_val
            cfg[cfg_key] = legacy_val

    def _set_bank_factor(self, cfg_key: str, legacy_key: str, value: float) -> None:
        val = self._as_float(value)
        if val is None or val <= 0:
            return
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        cfg = self._bank_charger_cfg()
        old = self._as_float(cfg.get(cfg_key, None))
        if old is not None and abs(old - val) < 1e-9:
            return
        cfg[cfg_key] = val
        proyecto[legacy_key] = val
        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)
        self._invalidate_bc_bundle()
        self._update_selection_tables()
        self._update_summary_table()

    def _on_bank_k1_changed(self, value: float) -> None:
        self._set_bank_factor("k1_margen", "bb_margen_diseno", value)

    def _on_bank_k2_changed(self, value: float) -> None:
        self._set_bank_factor("k2_altitud", "bb_k2_temp", value)

    def _on_bank_k3_changed(self, value: float) -> None:
        self._set_bank_factor("k3_envejecimiento", "bb_factor_envejec", value)

    def _get_battery_nominal_v(self) -> float:
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        v_nom = self._as_float(proyecto.get("bateria_tension_nominal", 0.0))
        return float(v_nom or 0.0)

    def _iter_material_batteries(self) -> list:
        lib = (self.data_model.library_data or {}).get("materiales", {})
        items = (lib.get("items", {}) if isinstance(lib, dict) else {})
        bats = items.get("batteries", []) if isinstance(items, dict) else []
        out = []
        seen = set()
        for b in bats:
            if not isinstance(b, dict):
                continue
            brand = str(
                b.get("brand")
                or b.get("marca")
                or b.get("Marca")
                or ""
            ).strip()
            model = str(
                b.get("model")
                or b.get("modelo")
                or b.get("Modelo")
                or ""
            ).strip()
            v_nom = (
                self._as_float(b.get("nominal_voltage_v"))
                or self._as_float(b.get("tension_nominal_v"))
                or self._as_float(b.get("Tensión Nominal [V]"))
                or self._as_float(b.get("tension_nominal"))
            )
            ah = (
                self._as_float(b.get("nominal_capacity_ah"))
                or self._as_float(b.get("capacity_ah"))
                or self._as_float(b.get("Ah"))
                or self._as_float(b.get("ah"))
            )
            ri = (
                self._as_float(b.get("ri_mohm"))
                or self._as_float(b.get("ri"))
                or self._as_float(b.get("internal_resistance_mohm"))
            )
            float_min = (
                self._as_float(b.get("float_min_vpc"))
                or self._as_float(b.get("float_min"))
                or self._as_float(b.get("v_float_min"))
            )
            rate = (
                self._as_float(b.get("rate"))
                or self._as_float(b.get("discharge_rate"))
                or self._as_float(b.get("c_rate"))
            )
            if not brand or not model or v_nom is None or ah is None:
                continue
            if v_nom <= 0 or ah <= 0:
                continue
            key = (brand.casefold(), model.casefold(), round(v_nom, 4), round(ah, 4))
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "marca": brand,
                    "modelo": model,
                    "v_nom": float(v_nom),
                    "ah": float(ah),
                    "ri_mohm": ri,
                    "float_min_vpc": float_min,
                    "rate": rate,
                }
            )
        out.sort(key=lambda x: (x["ah"], x["marca"].casefold(), x["modelo"].casefold()))
        return out

    def _edit_selection_cell(self, table: QTableWidget, row: int, col: int) -> None:
        if col != 1:
            return
        it = table.item(row, col)
        if it is None:
            return
        if (it.flags() & Qt.ItemIsEditable):
            table.editItem(it)

    def get_available_batteries(self, v_nom_cell: float):
        out = []
        for b in self._iter_material_batteries():
            if v_nom_cell > 0 and abs(float(b["v_nom"]) - float(v_nom_cell)) > 0.01:
                continue
            out.append(b)
        return out

    def _materials_battery_capacities(self, nominal_v: float | None = None):
        caps = []
        for b in self.get_available_batteries(float(nominal_v or 0.0)):
            caps.append(float(b["ah"]))
        return sorted(set([c for c in caps if c > 0]))

    def _materials_batteries_for_nominal(self, nominal_v: float):
        return self.get_available_batteries(float(nominal_v or 0.0))

    def pick_capacity_from_materials(self, required_ah: float, v_nom_cell: float):
        caps = self._materials_battery_capacities(v_nom_cell)
        req = float(required_ah or 0.0)
        if not caps:
            return {"selected_ah": None, "exact_match": False, "insufficient": False, "available": []}
        if req <= 0:
            return {"selected_ah": caps[0], "exact_match": True, "insufficient": False, "available": caps}

        exact = any(abs(c - req) <= 1e-9 for c in caps)
        for c in caps:
            if c >= req:
                return {
                    "selected_ah": c,
                    "exact_match": exact,
                    "insufficient": False,
                    "available": caps,
                }
        return {
            "selected_ah": caps[-1],
            "exact_match": exact,
            "insufficient": True,
            "available": caps,
        }

    @staticmethod
    def _fmt_ah(v: float | None) -> str:
        if v is None:
            return "—"
        if float(v).is_integer():
            return f"{int(v)}"
        return f"{float(v):.2f}"

    def _selected_battery_from_cfg(self, nominal_v: float):
        cfg = self._bank_charger_cfg()
        sel = cfg.get("battery_selected", {})
        if not isinstance(sel, dict):
            return None
        marca = str(sel.get("marca", "")).strip()
        modelo = str(sel.get("modelo", "")).strip()
        if not marca or not modelo:
            return None
        for b in self._materials_batteries_for_nominal(nominal_v):
            if b["marca"] == marca and b["modelo"] == modelo:
                return b
        return None

    def _get_selected_battery_ah(self, nominal_v: float) -> float | None:
        b = self._selected_battery_from_cfg(nominal_v)
        return float(b["ah"]) if b is not None else None

    def _find_default_battery_for_capacity(self, nominal_v: float, target_ah: float | None):
        batteries = self._materials_batteries_for_nominal(nominal_v)
        if not batteries:
            return None
        if target_ah is not None:
            for b in batteries:
                if abs(float(b["ah"]) - float(target_ah)) <= 1e-9:
                    return b
        return batteries[0]

    def _capacity_from_current_bundle(self) -> float | None:
        bundle = getattr(self, "_bc_bundle", None)
        if bundle is None:
            return None
        return self._as_float(getattr(bundle, "ah_commercial_str", None))

    def _refresh_battery_selector(self) -> None:
        nominal_v = self._get_battery_nominal_v()
        batteries = self._materials_batteries_for_nominal(nominal_v)
        selected = self._selected_battery_from_cfg(nominal_v)

        if selected is None:
            selected = self._find_default_battery_for_capacity(
                nominal_v,
                self._capacity_from_current_bundle(),
            )

        selected_brand = str(selected["marca"]).strip() if selected else ""
        selected_model = str(selected["modelo"]).strip() if selected else ""

        self.cmb_battery_brand.blockSignals(True)
        self.cmb_battery_model.blockSignals(True)
        try:
            self.cmb_battery_brand.clear()
            brands = sorted({b["marca"] for b in batteries}, key=lambda x: x.casefold())
            self.cmb_battery_brand.addItems(brands)
            if selected_brand in brands:
                self.cmb_battery_brand.setCurrentText(selected_brand)
            elif brands:
                self.cmb_battery_brand.setCurrentIndex(0)
            self._reload_model_combo(selected_model)
        finally:
            self.cmb_battery_brand.blockSignals(False)
            self.cmb_battery_model.blockSignals(False)

        enabled = bool(batteries)
        self.cmb_battery_brand.setEnabled(enabled)
        self.cmb_battery_model.setEnabled(enabled)
        self.btn_apply_battery.setEnabled(enabled)
        if not enabled:
            self.lbl_battery_ah.setText("—")

    def _reload_model_combo(self, preferred_model: str = "") -> None:
        nominal_v = self._get_battery_nominal_v()
        brand = str(self.cmb_battery_brand.currentText() or "").strip()
        batteries = [b for b in self._materials_batteries_for_nominal(nominal_v) if b["marca"] == brand]
        self.cmb_battery_model.clear()
        models = [b["modelo"] for b in batteries]
        self.cmb_battery_model.addItems(models)
        if preferred_model and preferred_model in models:
            self.cmb_battery_model.setCurrentText(preferred_model)
        elif models:
            self.cmb_battery_model.setCurrentIndex(0)
        self._on_battery_model_changed(self.cmb_battery_model.currentText())

    def _current_selected_battery(self):
        nominal_v = self._get_battery_nominal_v()
        brand = str(self.cmb_battery_brand.currentText() or "").strip()
        model = str(self.cmb_battery_model.currentText() or "").strip()
        for b in self._materials_batteries_for_nominal(nominal_v):
            if b["marca"] == brand and b["modelo"] == model:
                return b
        return None

    def _on_battery_brand_changed(self, _text: str) -> None:
        self.cmb_battery_model.blockSignals(True)
        try:
            self._reload_model_combo("")
        finally:
            self.cmb_battery_model.blockSignals(False)
        self._on_battery_model_changed(self.cmb_battery_model.currentText())

    def _on_battery_model_changed(self, _text: str) -> None:
        battery = self._current_selected_battery()
        if battery is None:
            self.lbl_battery_ah.setText("—")
            return
        self.lbl_battery_ah.setText(f"{self._fmt_ah(float(battery['ah']))} Ah")

    def _on_apply_battery_selected(self) -> None:
        battery = self._current_selected_battery()
        if battery is None:
            return
        cfg = self._bank_charger_cfg()
        cfg["battery_selected"] = {
            "marca": battery["marca"],
            "modelo": battery["modelo"],
            "ah": battery["ah"],
            "v_nom": battery["v_nom"],
            "ri_mohm": battery.get("ri_mohm"),
            "float_min_vpc": battery.get("float_min_vpc"),
            "rate": battery.get("rate"),
        }
        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)
        self._invalidate_bc_bundle()
        self._update_selection_tables()
        self._update_summary_table()

    def _materials_charger_currents(self, vdc: float, phases: str):
        lib = (self.data_model.library_data or {}).get("materiales", {})
        items = (lib.get("items", {}) if isinstance(lib, dict) else {})
        chgs = items.get("battery_banks", []) if isinstance(items, dict) else []
        out = []
        for c in chgs:
            if not isinstance(c, dict):
                continue
            if str(c.get("phases", "")).lower() != str(phases).lower():
                continue
            def _f(x):
                try:
                    return float(x)
                except Exception:
                    return None
            v1 = _f(c.get("dc_voltage_v_1", None))
            v2 = _f(c.get("dc_voltage_v_2", None))
            if not ((v1 is not None and abs(v1 - vdc) < 0.01) or (v2 is not None and abs(v2 - vdc) < 0.01)):
                continue
            try:
                out.append(float(c.get("output_current_a", 0)))
            except Exception:
                continue
        return sorted(set([x for x in out if x > 0]))

    def _paint_cell(self, item: QTableWidgetItem, kind: str):
        if item is None:
            return
        if kind == "editable":
            item.setBackground(_theme_color("EDITABLE_BG_STRONG", "#FFFFDC"))
        elif kind == "invalid":
            item.setBackground(_theme_color("INVALID_BG", "#FFD2D2"))
        else:
            item.setBackground(_theme_color("SURFACE", "#FFFFFF"))

    def _on_sel_charger_item_changed(self, item: QTableWidgetItem):
        if self._updating:
            return
        if item is None or item.column() != 1:
            return
        label_item = self.tbl_sel_charger.item(item.row(), 0)
        label = label_item.text().strip() if label_item else ""
        ov = self._get_bc_overrides()
        if label in ("Capacidad Comercial","Capacidad Comercial [Ah]"):
            try:
                val = float(item.text().replace(",", "."))
            except Exception:
                return
            ov["charger_commercial_a"] = val
            self._set_bc_overrides(ov)
            self._validate_selection_tables()
        if label in ("Constante pérdidas durante la carga", "Factor por altura geográfica"):
            try:
                val = float(item.text().replace(",", "."))
            except Exception:
                return
            if label.startswith("Constante"):
                ov["charger_k_loss"] = val
            else:
                ov["charger_k_alt"] = val
            self._set_bc_overrides(ov)

    def _validate_selection_tables(self):
        return self._controller.validate_selection_tables()

    def _get_ieee_section_nets(self):
        periods = list(self._cycle_periods_cache) if self._cycle_periods_cache else []
        rnd = getattr(self, "_cycle_random_cache", None)

        if not periods:
            return [], 0.0

        A = [float(p["A"]) for p in periods]
        n = len(A)

        def A_i(i):
            if i <= 0:
                return 0.0
            return A[i-1]

        nets = []
        store = self._get_ieee_kt_store()

        for s in range(1, n+1):
            pos_sum = 0.0
            neg_sum = 0.0
            missing = False

            for i in range(1, s+1):
                key = f"S{s}_P{i}"
                kt_val = store.get(key, "")
                try:
                    kt = float(str(kt_val).replace(",", ".")) if kt_val not in ("", None) else None
                except Exception:
                    kt = None

                if kt is None:
                    missing = True
                    continue

                dA = A_i(i) - A_i(i-1)
                if dA > 0:
                    pos_sum += dA * kt
                elif dA < 0:
                    neg_sum += dA * kt

            nets.append(None if missing else (pos_sum + neg_sum))

        # Random net (si existe)
        rnd_net = 0.0
        if rnd:
            key = "R"
            kt_val = store.get(key, "")
            try:
                kt = float(str(kt_val).replace(",", ".")) if kt_val not in ("", None) else None
            except Exception:
                kt = None

            if kt is not None:
                rnd_net = float(rnd["A"]) * kt  # dAR = AR - 0

        return nets, rnd_net

    # ===================== Selección / Resumen (UI) =====================
    
    def _on_charger_phases_changed(self, idx: int):
        ov = self._get_bc_overrides()
        ov["charger_phases"] = "monofasico" if idx == 0 else "trifasico"
        self._set_bc_overrides(ov)
        # Recalcular recomendaciones (sin pisar overrides manuales)
        if "charger_commercial_a" in ov:
            # si el usuario lo dejó manual, no pisar
            pass
        self._update_selection_tables()

    def _refresh_battery_warning(self) -> None:
        nominal_v = self._get_battery_nominal_v()
        bundle = getattr(self, "_bc_bundle", None)
        bank = getattr(bundle, "bank", None) if bundle is not None else None
        req = self._as_float(getattr(bank, "ah_required", None)) if bank is not None else None
        pick = self.pick_capacity_from_materials(float(req or 0.0), nominal_v)

        cap_sel = pick.get("selected_ah", None)
        exact_match = bool(pick.get("exact_match", False))
        insufficient = bool(pick.get("insufficient", False))
        caps = list(pick.get("available", []) or [])

        battery = self._current_selected_battery()
        marca_modelo = ""
        if battery is not None:
            marca_modelo = f"{battery.get('marca','')} {battery.get('modelo','')}".strip()
        if not marca_modelo:
            marca_modelo = "batería seleccionada"

        msgs = []
        if nominal_v > 0 and not caps:
            msgs.append(f"No hay baterías disponibles a {nominal_v:.0f}V en la librería cargada.")
        elif req and cap_sel:
            if insufficient:
                msgs.append(
                    f"Ah requerido {req:.0f}Ah excede máximo disponible {max(caps):.0f}Ah "
                    f"a {nominal_v:.0f}V. Se seleccionó {cap_sel:.0f}Ah ({marca_modelo}) "
                    "y el diseño podría no cumplir."
                )
            elif not exact_match:
                msgs.append(
                    f"No existe {req:.0f}Ah a {nominal_v:.0f}V. "
                    f"Se seleccionó {cap_sel:.0f}Ah ({marca_modelo})."
                )

        text = "\n".join(dict.fromkeys(msgs))
        self.lbl_battery_warning.setText(text)
        self.lbl_battery_warning.setVisible(bool(text.strip()))

    def _update_selection_tables(self):
        prev = getattr(self, "_updating", False)
        self._updating = True
        try:
            out = self._controller.update_selection_tables()
        finally:
            self._updating = prev
        self._refresh_battery_selector()
        self._refresh_battery_warning()
        return out

    def _update_summary_table(self):
        return self._controller.update_summary_table()

    def _on_summary_tag_changed(self, key: str, tag: str):
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        equip_tags = proyecto.get("equip_tags", {})
        if not isinstance(equip_tags, dict):
            equip_tags = {}
        if tag:
            equip_tags[key] = tag
        else:
            equip_tags.pop(key, None)
        proyecto["equip_tags"] = equip_tags
        self.data_model.mark_dirty(True)

    # ========================= API =========================
    def reload_from_project(self):
        self._controller.reset_loaded_flags()
        self._schedule_active_inner_tab_refresh()



    # ---- ScreenBase hooks (no functional changes intended) ----
    def load_from_model(self):
        """Load data from DataModel into this screen."""
        try:
            self._log_perfil_snapshot("load")
            self.reload_from_project()
        except Exception:
            # Avoid crashing during startup; errors will surface via existing UI pathways.
            pass

    def save_to_model(self):
        """Persist pending UI edits back into DataModel (if applicable)."""
        # This screen persists changes through its controllers/handlers.
        return
