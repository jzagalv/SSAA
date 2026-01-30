# -*- coding: utf-8 -*-
"""
Pestaña de resumen de consumos en Corriente Continua (C.C.).

Sólo considera componentes con:
    - tipo_consumo = "C.C. permanente"
    - tipo_consumo = "C.C. momentáneo"
    - tipo_consumo = "C.C. aleatorio"

Secciones:
1) Consumos permanentes:
   - Tabla con cada carga permanente en C.C.
   - Corriente calculada con P/Vcc.
   - Columna con % de utilización (global por defecto, editable opcional).
   - Columna con "I fuera de %" (I * (1 - pct/100)).
   - Totales al pie.
   - Botón para guardar captura de la tabla completa.

2) Consumos momentáneos:
   - Tabla con cargas momentáneas en C.C.
   - El usuario marca qué cargas incluir y a qué "Escenario" pertenecen.
   - SpinBox para definir N° de escenarios.
   - Tabla de resumen por escenario (con columna de Descripción editable).
   - Botones para guardar imagen de ambas tablas.

3) Consumos aleatorios:
   - Tabla con cargas "C.C. aleatorio" en C.C.
   - Columna de selección por checkbox.
   - Totales de P e I de los seleccionados.
   - Botón para guardar captura de la tabla completa.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QDoubleSpinBox, QSpinBox, QCheckBox,
    QFileDialog, QHeaderView, QComboBox, QTabWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QGuiApplication


from ui.common.state import save_header_state, restore_header_state
from screens.base import ScreenBase
from app.sections import Section
from functools import partial

from ui.table_utils import make_table_sortable

from .cc_consumption_controller import CCConsumptionController

from domain.cc_consumption import (
    get_model_gabinetes,
    get_vcc_nominal,
    get_vcc_for_currents,
    get_pct_global,
    get_usar_pct_global,
    get_num_escenarios,
    get_escenarios_desc,
    iter_cc_items,
    split_by_tipo,
    get_pct_for_permanent,
    compute_cc_permanentes_totals,
    compute_momentary_scenarios_full,
    compute_cc_aleatorios_totals,
)

import logging

log = logging.getLogger(__name__)


from screens.cc_consumption.widgets import (
    # columns
    PERM_COL_GAB, PERM_COL_TAG, PERM_COL_DESC, PERM_COL_PW, PERM_COL_PCT, PERM_COL_P_PERM, PERM_COL_I, PERM_COL_P_MOM, PERM_COL_I_OUT,
    MOM_COL_GAB, MOM_COL_TAG, MOM_COL_DESC, MOM_COL_PEFF, MOM_COL_I, MOM_COL_INCLUIR, MOM_COL_ESC,
    MOMR_COL_ESC, MOMR_COL_DESC, MOMR_COL_PT, MOMR_COL_IT,
    ALE_COL_SEL, ALE_COL_GAB, ALE_COL_TAG, ALE_COL_DESC, ALE_COL_PEFF, ALE_COL_I,
    # factories + render
    create_perm_table, create_mom_table, create_mom_summary_table, create_rand_table,
    load_permanentes, load_momentaneos, load_aleatorios,
)

from .tabs.permanentes_tab import PermanentesTabMixin
from .tabs.momentaneos_tab import MomentaneosTabMixin
from .tabs.aleatorios_tab import AleatoriosTabMixin


class CCConsumptionScreen(ScreenBase, PermanentesTabMixin, MomentaneosTabMixin, AleatoriosTabMixin):
    SECTION = Section.CC
    porcentaje_util_changed = pyqtSignal(float)   # <-- nueva señal
    def __init__(self, data_model, parent=None):
        super().__init__(data_model, parent=parent)
        self.data_model = data_model
        self._controller = CCConsumptionController(data_model)
        self._building = False  # para no disparar señales mientras se carga

        # Auto-refresh (sin botón): agrupa cambios rápidos (typing/spin) en un solo reload.
        self._auto_reload_timer = QTimer(self)
        self._auto_reload_timer.setSingleShot(True)
        self._auto_reload_timer.setInterval(250)
        self._auto_reload_timer.timeout.connect(self.reload_data)

        self._build_ui()
        self._restore_ui_state()
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(self._persist_ui_state)
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        # Startup-safe: do not compute totals during __init__. The orchestrator
        # will call reload_data() when a project is loaded or data changes.
        self.enter_safe_state()

    def enter_safe_state(self) -> None:
        """Put the screen in a safe empty state (no calculations, no dialogs)."""
        try:
            self._building = True
            # Clear tables to avoid showing stale data.
            for tbl in (getattr(self, 'tbl_perm', None), getattr(self, 'tbl_mom', None), getattr(self, 'tbl_mom_res', None), getattr(self, 'tbl_ale', None)):
                if tbl is not None:
                    tbl.setRowCount(0)
            # Show a non-blocking hint.
            if hasattr(self, 'lbl_empty_hint'):
                self.lbl_empty_hint.setVisible(True)
        finally:
            self._building = False

    def _restore_ui_state(self):
        """Restore per-user UI state (safe)."""
        try:
            restore_header_state(self.tbl_perm.horizontalHeader(), "cc_consumption.tbl_perm.header")
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def _persist_ui_state(self):
        """Persist per-user UI state (safe)."""
        try:
            save_header_state(self.tbl_perm.horizontalHeader(), "cc_consumption.tbl_perm.header")
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def _schedule_reload_data(self):
        """Programa un reload_data() 'debounced'.

        Reemplaza el botón 'Actualizar valores': ante cambios de parámetros
        (Vcc nominal, Vmin, % global, etc.) se recalcula automáticamente.
        """
        if getattr(self, "_building", False) or getattr(self, "_updating", False):
            return
        # Re-armar/actualizar tabla puede ser costoso, por eso se "debounced"
        # con un timer corto.
        try:
            self._auto_reload_timer.start()
        except Exception:
            self.reload_data()

    def showEvent(self, event):
        """Al mostrar la pantalla, refrescar automáticamente."""
        super().showEvent(event)
        self._schedule_reload_data()

    def _find_comp_by_id(self, comp_id: str):
        if not comp_id:
            return None
        for gab in self._iter_model_gabinetes():  # usa instalaciones["gabinetes"]
            for c in gab.get("components", []) or []:
                if c.get("id") == comp_id:
                    return c
        return None

    def set_debug_mode(self, enabled: bool):
        self._debug_mode = bool(enabled)
        self._apply_debug_tooltips()

    def _apply_debug_tooltips(self):
        self._apply_debug_to_table(self.tbl_perm, PERM_COL_TAG)
        self._apply_debug_to_table(self.tbl_mom, MOM_COL_TAG)
        self._apply_debug_to_table(self.tbl_ale, ALE_COL_TAG)

    def _apply_debug_to_table(self, table, tag_col: int):
        if table is None:
            return
        for r in range(table.rowCount()):
            it = table.item(r, tag_col)
            if not it:
                continue
            comp_id = it.data(Qt.UserRole)
            if getattr(self, "_debug_mode", False) and comp_id:
                it.setToolTip(f"ID consumo: {comp_id}")
            else:
                it.setToolTip("")

    # =========================================================
    # UI
    # =========================================================
    def _build_ui(self):
        root = QVBoxLayout(self)

        # Startup hint (non-blocking). Hidden automatically when data is loaded.
        self.lbl_empty_hint = QLabel(
            "Proyecto no cargado o datos incompletos.\n\n"
            "Carga un proyecto .ssaa o completa los datos en 'Proyecto', 'Consumos (gabinetes)' "
            "y 'Arquitectura SS/AA' para ver los totales en C.C."
        )
        self.lbl_empty_hint.setWordWrap(True)
        self.lbl_empty_hint.setProperty("mutedHint", True)
        self.lbl_empty_hint.setVisible(False)
        root.addWidget(self.lbl_empty_hint)

        # Widget de pestañas internas
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        # ================== Sección 1: Permanentes ==================
        self.grp_perm = QGroupBox("Consumos Permanentes en C.C.")
        g_perm = self.grp_perm
        v_perm = QVBoxLayout(g_perm)

        # Línea de tensión nominal y % utilización
        top_perm = QHBoxLayout()

        # --- Bloque Vnom / Vmin ---
        vbox_v = QVBoxLayout()

        row_vnom = QHBoxLayout()
        row_vnom.addWidget(QLabel("Tensión nominal C.C. [V]:"))
        self.lbl_vcc = QLabel("-")
        row_vnom.addWidget(self.lbl_vcc)
        row_vnom.addStretch()

        row_vmin = QHBoxLayout()
        row_vmin.addWidget(QLabel("Vmin para cálculo de corrientes [V]:"))
        self.lbl_vmin = QLabel("-")
        row_vmin.addWidget(self.lbl_vmin)
        row_vmin.addStretch()

        vbox_v.addLayout(row_vnom)
        vbox_v.addLayout(row_vmin)

        top_perm.addLayout(vbox_v)

        # --- Resto de controles ---
        top_perm.addSpacing(20)
        top_perm.addWidget(QLabel("% Utilización global:"))
        self.spin_pct_global = QDoubleSpinBox()
        self.spin_pct_global.setRange(0.0, 100.0)
        self.spin_pct_global.setDecimals(2)
        self.spin_pct_global.setSingleStep(1.0)
        top_perm.addWidget(self.spin_pct_global)

        self.chk_usar_global = QCheckBox("Usar % global en todas las cargas")
        self.chk_usar_global.setChecked(True)
        top_perm.addWidget(self.chk_usar_global)

        # (Auto-refresh) Eliminamos el botón "Actualizar datos". La vista se
        # actualiza automáticamente al cambiar parámetros o al mostrar la pestaña.

        top_perm.addStretch()
        v_perm.addLayout(top_perm)
        # Tabla de permanentes
        self.tbl_perm = create_perm_table(self)
        header_p = self.tbl_perm.horizontalHeader()
        header_p.setMinimumSectionSize(40)
        header_p.setStretchLastSection(False)
        make_table_sortable(self.tbl_perm)
        self.tbl_perm.verticalHeader().setDefaultSectionSize(26)

        # La tabla debe ocupar el alto disponible (ev el alto disponible (evita “aire” debajo)
        v_perm.addWidget(self.tbl_perm, 1)

        # Totales y botón imagen
        bottom_perm = QHBoxLayout()

        self.lbl_perm_total_p_total = QLabel("Total P total: 0.00 [W]")
        self.lbl_perm_total_p_perm = QLabel("Total P permanente: 0.00 [W]")
        self.lbl_perm_total_i = QLabel("Total I permanente: 0.00 [A]")
        self.lbl_perm_total_p_mom = QLabel("Total P momentánea: 0.00 [W]")
        self.lbl_perm_total_i_fuera = QLabel("Total I momentánea: 0.00 [A]")

        bottom_perm.addWidget(self.lbl_perm_total_p_total)
        bottom_perm.addSpacing(20)
        bottom_perm.addWidget(self.lbl_perm_total_p_perm)
        bottom_perm.addSpacing(20)
        bottom_perm.addWidget(self.lbl_perm_total_i)
        bottom_perm.addSpacing(30)
        bottom_perm.addWidget(self.lbl_perm_total_p_mom)
        bottom_perm.addSpacing(20)
        bottom_perm.addWidget(self.lbl_perm_total_i_fuera)

        bottom_perm.addStretch()
        self.btn_img_perm = QPushButton("Guardar imagen tabla permanentes…")
        bottom_perm.addWidget(self.btn_img_perm)
        v_perm.addLayout(bottom_perm)

        # --- Pestaña "Permanentes" ---
        perm_page = QWidget()
        perm_layout = QVBoxLayout(perm_page)
        perm_layout.addWidget(g_perm, 1)
        self.tabs.addTab(perm_page, "Permanentes")

        # ================== Sección 2: Momentáneos ==================
        self.grp_mom = QGroupBox("Consumos Momentáneos en C.C. – Escenarios")
        g_mom = self.grp_mom
        v_mom = QVBoxLayout(g_mom)

        top_mom = QHBoxLayout()
        top_mom.addWidget(QLabel("N° de escenarios:"))
        self.spin_escenarios = QSpinBox()
        self.spin_escenarios.setRange(1, 20)
        self.spin_escenarios.setValue(1)
        top_mom.addWidget(self.spin_escenarios)
        top_mom.addStretch()
        v_mom.addLayout(top_mom)
        # Tabla de cargas momentáneas
        self.tbl_mom = create_mom_table(self)
        self.tbl_mom.itemChanged.connect(self._on_mom_item_changed)
        header_m = self.tbl_mom.horizontalHeader()
        header_m.setMinimumSectionSize(40)
        header_m.setStretchLastSection(False)
        make_table_sortable(self.tbl_mom)
        self.tbl_mom.verticalHeader().setDefaultSectionSize(26)
        self.tbl_mom.setSortingEnabled(False)   # <-- CLAVE (tiene checkbox/combo)

        # Tabla principal ocupa el alto disponible
        v_mom.addWidget(self.tbl_mom, 3)

        # Tabla de resumen por escenario (con descripción)
        self.tbl_mom_resumen = create_mom_summary_table(self)
        header_mr = self.tbl_mom_resumen.horizontalHeader()

        header_mr.setSectionResizeMode(QHeaderView.Interactive)
        header_mr.setMinimumSectionSize(40)
        header_mr.setStretchLastSection(False)
        make_table_sortable(self.tbl_mom_resumen)
        self.tbl_mom_resumen.verticalHeader().setDefaultSectionSize(24)
        self.tbl_mom_resumen.verticalHeader().setDefaultSectionSize(26)
        self.tbl_mom_resumen.verticalHeader().setDefaultSectionSize(26)
        v_mom.addWidget(self.tbl_mom_resumen, 1)

        bottom_mom = QHBoxLayout()
        bottom_mom.addStretch()
        self.btn_img_mom_cargas = QPushButton("Imagen tabla momentáneos…")
        self.btn_img_mom_esc = QPushButton("Imagen tabla escenarios…")
        bottom_mom.addWidget(self.btn_img_mom_cargas)
        bottom_mom.addWidget(self.btn_img_mom_esc)
        v_mom.addLayout(bottom_mom)

        # --- Pestaña "Momentáneos" ---
        mom_page = QWidget()
        mom_layout = QVBoxLayout(mom_page)
        mom_layout.addWidget(g_mom, 1)
        self.tabs.addTab(mom_page, "Momentáneos")


        # ================== Sección 3: Aleatorios ==================
        self.grp_ale = QGroupBox("Consumos Aleatorios en C.C.")
        g_ale = self.grp_ale
        v_ale = QVBoxLayout(g_ale)
        self.tbl_ale = create_rand_table(self)
        header_a = self.tbl_ale.horizontalHeader()

        header_a.setSectionResizeMode(QHeaderView.Interactive)
        header_a.setMinimumSectionSize(40)
        header_a.setStretchLastSection(False)
        make_table_sortable(self.tbl_ale)
        self.tbl_ale.verticalHeader().setDefaultSectionSize(26)
        self.tbl_ale.verticalHeader().setDefaultSectionSize(26)
        self.tbl_ale.verticalHeader().setDefaultSectionSize(26)
        self.tbl_ale.setSortingEnabled(False)   # <-- recomendado
        v_ale.addWidget(self.tbl_ale, 1)

        bottom_ale = QHBoxLayout()
        self.lbl_ale_total_p = QLabel("Total P aleatoria seleccionada: 0.00 [W]")
        self.lbl_ale_total_i = QLabel("Total I aleatoria seleccionada: 0.00 [A]")
        bottom_ale.addWidget(self.lbl_ale_total_p)
        bottom_ale.addSpacing(30)
        bottom_ale.addWidget(self.lbl_ale_total_i)
        bottom_ale.addStretch()
        self.btn_img_ale = QPushButton("Guardar imagen tabla aleatorios…")
        bottom_ale.addWidget(self.btn_img_ale)
        v_ale.addLayout(bottom_ale)

        # --- Pestaña "Aleatorios" ---
        ale_page = QWidget()
        ale_layout = QVBoxLayout(ale_page)
        ale_layout.addWidget(g_ale, 1)
        self.tabs.addTab(ale_page, "Aleatorios")

        # No agregamos stretch extra: el contenido ya expande

        # ================== Conexiones ==================
        # (auto-refresh) ya no hay botón manual.
        self.spin_pct_global.valueChanged.connect(self._on_global_pct_changed)
        self.spin_pct_global.valueChanged.connect(self._schedule_reload_data)
        self.chk_usar_global.toggled.connect(self._on_chk_usar_global_toggled)
        self.chk_usar_global.toggled.connect(self._schedule_reload_data)
        self.tbl_perm.itemChanged.connect(self._on_perm_item_changed)

        self.tbl_mom_resumen.itemChanged.connect(self._on_mom_resumen_item_changed)
        self.spin_escenarios.valueChanged.connect(self._rebuild_momentary_scenarios)

        self.btn_img_perm.clicked.connect(
            lambda: self._save_section_as_image(self.grp_perm, self.tbl_perm, "consumos_permanentes.png")
        )
        self.btn_img_mom_cargas.clicked.connect(
            lambda: self._save_section_as_image(self.grp_mom, self.tbl_mom, "consumos_momentaneos.png")
        )
        self.btn_img_mom_esc.clicked.connect(
            lambda: self._save_section_as_image(self.grp_mom, self.tbl_mom_resumen, "escenarios_momentaneos.png")
        )
        self.btn_img_ale.clicked.connect(
            lambda: self._save_section_as_image(self.grp_ale, self.tbl_ale, "consumos_aleatorios.png")
        )

    def refresh_from_model(self):
        proyecto = getattr(self.data_model, "proyecto", {}) or {}

        def _to_float(x, default=0.0):
            try:
                if x is None:
                    return default
                if isinstance(x, str):
                    x = x.strip().replace(",", ".")
                    if x == "":
                        return default
                return float(x)
            except Exception:
                return default

        v_nom = _to_float(proyecto.get("dc_nominal_voltage"), 0.0)

        # Toma el porcentaje desde el proyecto (ajusta la key si tu proyecto usa otro nombre)
        vmin_pct = _to_float(
            proyecto.get("dc_vmin_pct", proyecto.get("tension_minima_pct", 15.0)),
            15.0
        )

        # Calcula Vmin
        vmin_calc = v_nom * (1.0 - vmin_pct / 100.0) if v_nom > 0 else 0.0

        # --- SETEAR EN WIDGETS SOLO SI EXISTEN ---
        # 1) Tensión nominal (si tienes un QLineEdit/label asociado)
        for attr in ("edit_vnom", "txt_vnom", "le_vnom", "inp_vnom", "lbl_vnom", "lbl_vmin"):
            w = getattr(self, attr, None)
            if w is not None and hasattr(w, "setText"):
                w.setText(f"{v_nom:.2f}" if v_nom > 0 else "")
                break

        # 2) Vmin para cálculo: prueba varios nombres comunes / tuyos
        for attr in ("edit_vmin_calc", "edit_vmin", "txt_vmin", "le_vmin", "inp_vmin", "lbl_vmin_calc", "lbl_vmin"):
            w = getattr(self, attr, None)
            if w is not None and hasattr(w, "setText"):
                w.setText(f"{vmin_calc:.2f}" if vmin_calc > 0 else "")
                return

        # Si llegamos aquí, no encontramos el widget. No crashear: solo log.
        print("[CCConsumptionScreen] No se encontró el widget para Vmin (revisa el nombre del QLineEdit/label).")


    # =========================================================
    # Helpers numéricos / de datos
    # =========================================================
    @staticmethod
    def _to_float(val, default=0.0):
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        if not s or s == "----":
            return default
        s = s.replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return default

    def _set_project_value(self, key: str, value):
        # Delegar en controller (centraliza mutaciones y dirty flag)
        return self._controller.set_project_value(key, value)

    def _auto_resize(self, table: QTableWidget, min_widths: dict = None):
        """Ajusta las columnas al contenido con un ancho mínimo por columna."""
        if table is None:
            return
        if min_widths is None:
            min_widths = {}
        table.resizeColumnsToContents()
        header = table.horizontalHeader()
        for col in range(table.columnCount()):
            current = header.sectionSize(col)
            minw = min_widths.get(col, 60)
            if current < minw:
                header.resizeSection(col, minw)

    def load_from_model(self):
        # ScreenBase hook: cargar datos desde el modelo a la UI
        self.reload_data()

    def save_to_model(self):
        # ScreenBase hook: persistir ediciones pendientes al modelo
        self.commit_pending_edits()

    def reload_data(self):
        self.commit_pending_edits()
        self._building = True

        # --- Proyecto / modelo ---
        proj = getattr(self.data_model, "proyecto", {}) or {}
        gabinetes = get_model_gabinetes(self.data_model)

        # Startup-safe / empty project: if required data is missing, avoid any
        # heavy computations and show a non-blocking hint.
        try:
            vcc_nom = get_vcc_nominal(proj)
            vcc_for_currents = get_vcc_for_currents(proj)
        except Exception:
            vcc_nom = None
            vcc_for_currents = None

        if (vcc_nom is None) or (vcc_for_currents is None):
            # Clear visible fields
            self.lbl_vcc.setText("-")
            self.lbl_vmin.setText("-")
            if hasattr(self, 'lbl_empty_hint'):
                self.lbl_empty_hint.setVisible(True)
            for tbl in (getattr(self, 'tbl_perm', None), getattr(self, 'tbl_mom', None), getattr(self, 'tbl_mom_res', None), getattr(self, 'tbl_ale', None)):
                if tbl is not None:
                    tbl.setRowCount(0)
            self._building = False
            return

        # If we got here we have voltages -> hide startup hint.
        if hasattr(self, 'lbl_empty_hint'):
            self.lbl_empty_hint.setVisible(False)

        # --- Tensiones (vnom / vmin) desde dominio ---
        self.lbl_vcc.setText(f"{float(vcc_nom):.2f}")

        self._vcc_for_currents = float(vcc_for_currents)
        self.lbl_vmin.setText(f"{self._vcc_for_currents:.2f}")

        # --- % global y modo global desde dominio ---
        pct_global = get_pct_global(proj)
        self.spin_pct_global.setValue(pct_global)

        usar_global = get_usar_pct_global(proj)
        self.chk_usar_global.setChecked(usar_global)

        # --- escenarios desde dominio ---
        n_esc = get_num_escenarios(proj)
        self.spin_escenarios.setValue(n_esc)

        # --- Items C.C. desde dominio ---
        all_items = iter_cc_items(proj, gabinetes)
        permanentes, momentaneos, aleatorios = split_by_tipo(all_items)

        # --- Cargar tablas ---
        self._load_permanentes(permanentes, proj)            # <-- cambiado
        self._load_momentaneos(momentaneos) # <-- igual, pero ahora recibe CCItem
        self._load_aleatorios(aleatorios)                    # <-- igual, pero ahora recibe CCItem

        self._building = False

        # --- Recalcular displays ---
        self._update_permanent_totals()
        self._rebuild_momentary_scenarios()
        self._update_momentary_summary_display()
        self._update_aleatory_totals()
        self._apply_debug_tooltips()

        # --- Derived totals for other screens/reports (best-effort) ---
        # Keep behavior identical by using CalcService (domain-backed).
        try:
            svc = getattr(self.data_model, "calc_service", None)
            if svc is not None:
                svc.recalc_cc()
        except Exception:
            log.debug("Failed to recalc CC via CalcService (best-effort).", exc_info=True)

    # =========================================================
    # Permanentes
    # =========================================================
    def _on_chk_usar_global_toggled(self, checked):
        if self._building:
            return

        # Guardar en el modelo
        proj = getattr(self.data_model, "proyecto", {})
        self._controller.set_use_pct_global(bool(checked))
        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)

        self._apply_global_pct_mode()

    def commit_pending_edits(self):
        """Solo fuerza commit del editor activo (NO recalcula ni llama totales)."""
        self._commit_table_edits()
        self._persist_scenario_descs_from_table()

    def _commit_table_edits(self):
        """
        Fuerza commit REAL de cualquier celda en edición.
        Sin esto, el texto puede quedar en el editor y NO en el QTableWidgetItem,
        por lo que al guardar se va el valor antiguo.
        """
        from PyQt5.QtWidgets import QApplication, QAbstractItemDelegate, QAbstractItemView

        app = QApplication.instance()

        for tbl in (
            getattr(self, "tbl_perm", None),
            getattr(self, "tbl_mom", None),
            getattr(self, "tbl_mom_resumen", None),  # ✅ OJO: este es el nombre correcto
            getattr(self, "tbl_ale", None),
        ):
            if tbl is None:
                continue

            if tbl.state() == QAbstractItemView.EditingState:
                editor = app.focusWidget()
                try:
                    # Fuerza que el delegate vuelque el editor al item/model
                    tbl.closeEditor(editor, QAbstractItemDelegate.SubmitModelCache)
                except Exception:
                    import logging
                    logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        try:
            app.processEvents()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)


        # Procesar eventos ayuda a que el commit ocurra antes de guardar
        try:
            app.processEvents()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def _save_section_as_image(self, container, table, default_name: str):
        """
        Captura una sección completa (el QGroupBox 'container'),
        expandiendo antes la tabla 'table' para que se vea completa.
        """
        if container is None or table is None:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar sección como imagen",
            default_name,
            "PNG (*.png)"
        )
        if not path:
            return

        # ---------- 1) Tamaño total de la tabla (todas las filas/columnas) ----------
        vh = table.verticalHeader()
        hh = table.horizontalHeader()
        frame = table.frameWidth() * 2

        width_table = vh.width() + frame
        for col in range(table.columnCount()):
            width_table += table.columnWidth(col)

        height_table = hh.height() + frame
        for row in range(table.rowCount()):
            height_table += table.rowHeight(row)

        # ---------- 2) Guardar estado original de tabla y contenedor ----------
        orig_table_size = table.size()
        orig_table_min = table.minimumSize()
        orig_h_scroll = table.horizontalScrollBarPolicy()
        orig_v_scroll = table.verticalScrollBarPolicy()

        orig_cont_size = container.size()
        orig_cont_min = container.minimumSize()

        # ---------- 3) Expandir tabla y contenedor ----------
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setMinimumSize(width_table, height_table)
        table.resize(width_table, height_table)

        # Hacemos que el groupbox crezca para envolver la tabla completa
        container.adjustSize()
        cont_hint = container.sizeHint()
        container.setMinimumSize(cont_hint)
        container.resize(cont_hint)
        container.repaint()

        # ---------- 4) Capturar el groupbox completo ----------
        pix: QPixmap = container.grab()
        pix.save(path, "PNG")

        # Copiar también al portapapeles
        try:
            QGuiApplication.clipboard().setPixmap(pix)
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
        # ---------- 5) Restaurar estados originales ----------
        table.setMinimumSize(orig_table_min)
        table.resize(orig_table_size)
        table.setHorizontalScrollBarPolicy(orig_h_scroll)
        table.setVerticalScrollBarPolicy(orig_v_scroll)

        container.setMinimumSize(orig_cont_min)
        container.resize(orig_cont_size)
        container.repaint()

    def reload_from_project(self):
        p = getattr(self.data_model, "proyecto", {}) or {}

        # 1) leer Vnom y %min
        try:
            v_nom = float(str(p.get("dc_nominal_voltage", 0)).replace(",", ".") or 0)
        except Exception:
            v_nom = 0.0

        try:
            min_pct = float(str(p.get("min_voltaje_cc", 0)).replace(",", ".") or 0)
        except Exception:
            min_pct = 0.0

        # 2) calcular Vmin
        v_min = v_nom * (1.0 - min_pct / 100.0) if v_nom > 0 else 0.0

        # 3) pintar UI
        self.txt_vnom.setText(f"{v_nom:.2f}" if v_nom > 0 else "")
        self.txt_vmin_calc.setText(f"{v_min:.2f}" if v_min > 0 else "")
