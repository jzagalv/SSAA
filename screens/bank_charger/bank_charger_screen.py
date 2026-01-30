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

from screens.base import ScreenBase
from app.sections import Section

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QPushButton, QInputDialog, QMessageBox,
    QTabWidget, QSplitter
)

from PyQt5.QtGui import QColor
from .widgets.duty_cycle_plot_widget import DutyCyclePlotWidget
from .bank_charger_export import export_all_one_click, save_widget_screenshot
from .bank_charger_controller import BankChargerController
from PyQt5.QtWidgets import QAbstractItemView

from services.ssaa_engine import SSAAEngine

from domain.cc_consumption import (
    get_model_gabinetes as cc_get_model_gabinetes,
    compute_cc_profile_totals,
    compute_momentary_from_permanents,
    compute_momentary_scenarios,
)

import logging

DURACION_MIN_GRAFICA_MIN = 10.0
CODE_L1 = "L1"
CODE_LAL = "L(al)"
CODE_LMOM_AUTO = "L2"
DESC_LMOM_AUTO = "Carga Momentáneas Equipos C&P"


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
        self._fill_datos_sistema()
        self._fill_comprobacion()
        # 1) Si existe perfil en proyecto, lo cargamos. Si no, creamos defaults.
        proyecto = getattr(self.data_model, "proyecto", {}) or {}
        if proyecto.get("perfil_cargas"):
            self._load_perfil_cargas_from_model()
        else:
            self._fill_perfil_cargas(save_to_model=True)

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

        self._connect_signals()
        # Startup policy: NEVER run heavy calculations nor show blocking dialogs during __init__.
        # The SectionOrchestrator will refresh/recalculate after a project is loaded or when sections change.
        self._render_startup_state()

        self._schedule_updates()

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
        self.tbl_datos = QTableWidget()
        self.tbl_datos.setColumnCount(2)
        self.tbl_datos.setHorizontalHeaderLabels(["Característica", "Valor"])
        self.tbl_datos.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_datos.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_datos.verticalHeader().setVisible(False)
        self.btn_cap_tbl_datos = QPushButton("Guardar captura")
        self.btn_cap_tbl_datos.clicked.connect(lambda: self._save_widget_screenshot(self.tbl_datos, "tabla_datos_del_sistema"))
        v_datos.addWidget(self.btn_cap_tbl_datos)
        v_datos.addWidget(self.tbl_datos)
        self.grp_datos.setLayout(v_datos)

        self.grp_comp = QGroupBox("Comprobación")
        v_comp = QVBoxLayout()
        self.tbl_comp = QTableWidget()
        self.tbl_comp.setColumnCount(2)
        self.tbl_comp.setHorizontalHeaderLabels(["Parámetro", "Valor"])
        self.tbl_comp.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_comp.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_comp.verticalHeader().setVisible(False)
        self.btn_cap_tbl_comp = QPushButton("Guardar captura")
        self.btn_cap_tbl_comp.clicked.connect(lambda: self._save_widget_screenshot(self.tbl_comp, "tabla_comprobacion"))
        v_comp.addWidget(self.btn_cap_tbl_comp)
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
        self.btn_add_area = QPushButton("Agregar carga")
        self.btn_add_from_scenario = QPushButton("Agregar desde escenario C.C.")
        self.btn_del_area = QPushButton("Eliminar carga seleccionada")
        btn_row.addWidget(self.btn_add_area)
        btn_row.addWidget(self.btn_add_from_scenario)
        btn_row.addWidget(self.btn_del_area)
        btn_row.addStretch()
        v_cargas.addLayout(btn_row)

        self.tbl_cargas = QTableWidget()
        self.tbl_cargas.setColumnCount(6)
        self.tbl_cargas.setHorizontalHeaderLabels(
            ["Ítem", "Descripción", "P [W]", "I [A]", "Inicio [min]", "Duración [min]"]
        )
        self.tbl_cargas.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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
        self.tbl_cycle.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_cycle.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_cycle.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_cycle.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
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
        self.tbl_ieee.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_ieee.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl_ieee.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_ieee.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tbl_ieee.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tbl_ieee.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.tbl_ieee.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.tbl_ieee.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
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
        self.tbl_sel_bank.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_sel_bank.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_sel_bank.verticalHeader().setVisible(False)
        self.btn_cap_tbl_sel_bank = QPushButton("Guardar captura de tabla")
        self.btn_cap_tbl_sel_bank.clicked.connect(lambda: self._save_widget_screenshot(self.tbl_sel_bank, "tabla_seleccion_banco"))
        v_sb.addWidget(self.btn_cap_tbl_sel_bank)
        v_sb.addWidget(self.tbl_sel_bank)

        # Cargador de baterías
        self.grp_sel_charger = QGroupBox("Selección Cargador de Baterías")
        v_sc = QVBoxLayout(self.grp_sel_charger)
        self.tbl_sel_charger = QTableWidget()
        self.tbl_sel_charger.setColumnCount(2)
        self.tbl_sel_charger.setHorizontalHeaderLabels(["Parámetro", "Valor"])
        self.tbl_sel_charger.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_sel_charger.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
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
        self.btn_edit_factors = QPushButton("Editar factores…")
        self.btn_edit_factors.setVisible(False)  # edición directa en tablas
        self.btn_export_all = QPushButton("Exportar todo (un clic)")
        # Edición directa en tablas de selección
        self.tbl_sel_bank.itemChanged.connect(self._on_sel_bank_item_changed)
        self.tbl_sel_charger.itemChanged.connect(self._on_sel_charger_item_changed)
        self.tbl_sel_bank.cellDoubleClicked.connect(lambda r,c: self._edit_selection_cell(self.tbl_sel_bank, r, c))
        self.tbl_sel_charger.cellDoubleClicked.connect(lambda r,c: self._edit_selection_cell(self.tbl_sel_charger, r, c))
        btns.addWidget(self.btn_edit_factors)
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
        self.tbl_summary.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl_summary.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl_summary.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_summary.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
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

        self.btn_add_area.clicked.connect(self._add_area_row)
        self.btn_add_from_scenario.clicked.connect(self._add_area_from_scenario)
        self.btn_del_area.clicked.connect(self._remove_selected_area)
        
        self.btn_edit_factors.clicked.connect(self._edit_factors_dialog)
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
        periods = list(getattr(self, "_cycle_periods_cache", []) or [])
        rnd = getattr(self, "_cycle_random_cache", None)

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
                cs.recalc_bank_charger(periods=periods, rnd=rnd, i_perm=float(i_perm or 0.0))
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

    def _edit_factors_dialog(self):
        self.commit_pending_edits()
        proyecto = getattr(self.data_model, "proyecto", {}) or {}

        def getd(title, label, key, default, decimals=2, minv=0.0, maxv=999.0):
            cur = default
            try:
                cur = float(str(proyecto.get(key, default)).replace(",", "."))
            except Exception:
                cur = float(default)
            val, ok = QInputDialog.getDouble(self, title, label, cur, minv, maxv, decimals)
            if ok:
                proyecto[key] = val
            return ok

        # Banco
        if not getd("Factores Banco", "K2 Temperatura", "bb_k2_temp", 1.0): return
        if not getd("Factores Banco", "Margen de diseño", "bb_margen_diseno", 1.15): return
        if not getd("Factores Banco", "Factor envejecimiento", "bb_factor_envejec", 1.25): return

        # Cargador
        if not getd("Factores Cargador", "Tiempo recarga (h)", "charger_t_rec_h", 10.0, decimals=0, minv=1.0, maxv=999.0): return
        if not getd("Factores Cargador", "K pérdidas", "charger_k_loss", 1.15): return
        if not getd("Factores Cargador", "K altura", "charger_k_alt", 1.0): return
        if not getd("Factores Cargador", "K temperatura", "charger_k_temp", 1.0): return
        if not getd("Factores Cargador", "K seguridad", "charger_k_seg", 1.25): return
        if not getd("Factores Cargador", "Eficiencia (0-1)", "charger_eff", 0.90, decimals=2, minv=0.1, maxv=1.0): return

        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)

        self._update_selection_tables()
        self._update_summary_table()
    
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
            item.setBackground(QColor(255, 249, 196))
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
        else:
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)

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

    def _persist_perfil_cargas(self):
        # Kept for backward compatibility (other modules call this).
        try:
            self._controller.pipeline.on_profile_changed()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error al persistir Perfil de cargas",
                f"Ocurrió un error al persistir/actualizar el Perfil de cargas.\n\n{e}",
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

            # (1.4) Número de celdas (Comprobación) = ceil(N sys). Editable.
            # Si el usuario ya puso uno, lo mantenemos; si no, ponemos el ceil.
            n_user_in = self._read_float_cell(self.tbl_comp, 0, 1)
            if n_user_in and n_user_in > 0:
                n_user = int(math.ceil(float(n_user_in)))
            else:
                n_user = int(math.ceil(float(n_cells_sys))) if n_cells_sys != "" else 0

            # Pintar N sys en tabla datos (fila 7)
            self._set_cell(self.tbl_datos, 7, 1, fnum(n_cells_sys, 2) if n_cells_sys != "" else "", editable=False)

            # (1.5) Tensión final por celda calculada = Vmin / N_user
            v_cell_min_calc = ""
            try:
                if res.v_min is not None and n_user:
                    v_cell_min_calc = float(res.v_min) / float(n_user)
            except Exception:
                v_cell_min_calc = ""

            self._set_cell(self.tbl_datos, 5, 1, fnum(v_cell_min_calc, 2) if v_cell_min_calc != "" else "", editable=False)

            # “Seleccionada” = combo (si existe)
            #self._set_cell(self.tbl_datos, 5, 1, fnum(v_cell_sel, 3) if v_cell_sel is not None else "", editable=False)
            self._set_table_value_or_widget(self.tbl_datos, 6, 1, fnum(v_cell_sel, 3) if v_cell_sel is not None else "")

            # 7) Pintar TABLA COMPROBACIÓN (user)
            self._set_cell(self.tbl_comp, 0, 1, fnum(n_user, 2) if n_user else "", editable=True)

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
            (f"Tensión máxima (+{v_max_pct} %) [V]", v_max_val),
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

        return compute_momentary_scenarios(proyecto=proyecto, gabinetes=gabinetes, vmin=vmin)

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

    def _add_area_row(self):
        row_lal = self._row_index_of_lal()
        row = row_lal if row_lal >= 0 else self.tbl_cargas.rowCount()

        self._updating = True
        try:
            self.tbl_cargas.insertRow(row)
            code = self._next_load_id()
            defaults = [code, "", "—", "—", "—", "—"]
            for c, v in enumerate(defaults):
                self.tbl_cargas.setItem(row, c, QTableWidgetItem(str(v)))
        finally:
            self._updating = False

        self._apply_perfil_editability()
        self._refresh_perfil_autocalc()
        self._save_perfil_cargas_to_model()
        self._update_cycle_table()
        self._update_ieee485_table()
        self._schedule_updates()

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

        self._refresh_perfil_autocalc()
        self._save_perfil_cargas_to_model()
        self._update_cycle_table()
        self._update_ieee485_table()
        self._schedule_updates()

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

        opciones = []
        for esc in sorted(escenarios.keys()):
            data = escenarios[esc]
            p = float(data.get("p_total", 0.0))
            i = float(data.get("i_total", 0.0))
            d = descs.get(str(esc), "")
            label = f"Escenario {esc} – {d} (P={p:.1f} W, I={i:.2f} A)"
            opciones.append((label, esc, p, i, d))

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
        finally:
            self._updating = False

        self._apply_perfil_editability()
        self._refresh_perfil_autocalc()
        self._save_perfil_cargas_to_model()
        self._update_cycle_table()
        self._update_ieee485_table()
        self._schedule_updates()

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
        return self._controller.update_profile_chart()

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

    def _edit_selection_cell(self, table: QTableWidget, row: int, col: int) -> None:
        if col != 1:
            return
        it = table.item(row, col)
        if it is None:
            return
        if (it.flags() & Qt.ItemIsEditable):
            table.editItem(it)

    def _materials_battery_capacities(self):
        lib = (self.data_model.library_data or {}).get("materiales", {})
        items = (lib.get("items", {}) if isinstance(lib, dict) else {})
        bats = items.get("batteries", []) if isinstance(items, dict) else []
        caps = []
        for b in bats:
            if not isinstance(b, dict):
                continue
            try:
                caps.append(float(b.get("nominal_capacity_ah", 0)))
            except Exception:
                continue
        return sorted(set([c for c in caps if c > 0]))

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

    def _nearest_ge(self, values, target):
        for v in values:
            if v >= target:
                return v
        return None

    def _paint_cell(self, item: QTableWidgetItem, kind: str):
        if item is None:
            return
        if kind == "editable":
            item.setBackground(QColor(255, 255, 220))
        elif kind == "invalid":
            item.setBackground(QColor(255, 210, 210))
        else:
            item.setBackground(QColor(255, 255, 255))

    def _on_sel_bank_item_changed(self, item: QTableWidgetItem):
        if item is None or item.column() != 1:
            return
        label_item = self.tbl_sel_bank.item(item.row(), 0)
        label = label_item.text().strip() if label_item else ""
        ov = self._get_bc_overrides()
        if label in ("Capacidad Comercial","Capacidad Comercial [Ah]"):
            try:
                val = float(item.text().replace(",", "."))
            except Exception:
                return
            ov["bank_commercial_ah"] = val
            self._set_bc_overrides(ov)
            self._validate_selection_tables()
        # otros factores editables
        if label in ("Factor de Envejecimiento",):
            try:
                val = float(item.text().replace(",", "."))
            except Exception:
                return
            ov["bb_factor_envejec"] = val
            self._set_bc_overrides(ov)

    def _on_sel_charger_item_changed(self, item: QTableWidgetItem):
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

    def _round_commercial(self, value: float, step=10, mode="ceil"):
        if value is None:
            return "—"
        try:
            v = float(value)
        except Exception:
            return "—"
        if v <= 0:
            return "—"

        step = float(step) if step else 10.0

        if mode == "ceil":
            return int(math.ceil(v / step) * step)
        if mode == "floor":
            return int(math.floor(v / step) * step)
        # nearest
        return int(round(v / step) * step)

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

    def _make_selection_editable(self):
        # Banco: Capacidad Comercial editable; Factor envejecimiento editable
        for r in range(self.tbl_sel_bank.rowCount()):
            l = self.tbl_sel_bank.item(r, 0)
            v = self.tbl_sel_bank.item(r, 1)
            if not l or not v:
                continue
            lab = l.text().strip()
            if lab in ("Capacidad Comercial [Ah]", "Capacidad Comercial"):
                v.setFlags(v.flags() | Qt.ItemIsEditable)
                self._paint_cell(v, "editable")
                l.setFlags(l.flags() & ~Qt.ItemIsEditable)
            if lab in ("Factor de Envejecimiento",):
                v.setFlags(v.flags() | Qt.ItemIsEditable)
                self._paint_cell(v, "editable")
        # Cargador: pérdidas/altura y Capacidad Comercial editable
        for r in range(self.tbl_sel_charger.rowCount()):
            l = self.tbl_sel_charger.item(r, 0)
            v = self.tbl_sel_charger.item(r, 1)
            if not l or not v:
                continue
            lab = l.text().strip()
            if lab in ("Capacidad Comercial [A]", "Capacidad Comercial"):
                v.setFlags(v.flags() | Qt.ItemIsEditable)
                self._paint_cell(v, "editable")
            if lab in ("Constante pérdidas durante la carga", "Factor por altura geográfica"):
                v.setFlags(v.flags() | Qt.ItemIsEditable)
                self._paint_cell(v, "editable")

    def _update_selection_tables(self):
        return self._controller.update_selection_tables()

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
        return self._controller.reload_from_project()

    def _ensure_auto_momentary_load_in_profile(self, save_to_model: bool = True):
        return self._controller.ensure_auto_momentary_load_in_profile(save_to_model)



    # ---- ScreenBase hooks (no functional changes intended) ----
    def load_from_model(self):
        """Load data from DataModel into this screen."""
        try:
            self.reload_from_project()
        except Exception:
            # Avoid crashing during startup; errors will surface via existing UI pathways.
            pass

    def save_to_model(self):
        """Persist pending UI edits back into DataModel (if applicable)."""
        # This screen persists changes through its controllers/handlers.
        return