# -*- coding: utf-8 -*-
"""
Pestaña de resumen de consumos en Corriente Continua (C.C.).

SÃ³lo considera componentes con:
    - tipo_consumo = "C.C. permanente"
    - tipo_consumo = "C.C. momentÃ¡neo"
    - tipo_consumo = "C.C. aleatorio"

Secciones:
1) Consumos permanentes:
   - Tabla con cada carga permanente en C.C.
   - Corriente calculada con P/Vcc.
   - Columna con % de utilizaciÃ³n (global por defecto, editable opcional).
   - Columna con "I fuera de %" (I * (1 - pct/100)).
   - Totales al pie.
   - BotÃ³n para guardar captura de la tabla completa.

2) Consumos momentÃ¡neos:
   - Tabla con cargas momentÃ¡neas en C.C.
   - El usuario marca quÃ© cargas incluir y a quÃ© "Escenario" pertenecen.
   - SpinBox para definir N° de escenarios.
   - Tabla de resumen por escenario (con columna de DescripciÃ³n editable).
   - Botones para guardar imagen de ambas tablas.

3) Consumos aleatorios:
   - Tabla con cargas "C.C. aleatorio" en C.C.
   - Columna de selecciÃ³n por checkbox.
   - Totales de P e I de los seleccionados.
   - BotÃ³n para guardar captura de la tabla completa.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QDoubleSpinBox, QSpinBox, QCheckBox,
    QFileDialog, QHeaderView, QTabWidget, QTableView, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QGuiApplication
from ui.utils.table_utils import configure_table_autoresize
from datetime import datetime


from ui.common.state import save_header_state, restore_header_state
from screens.base import ScreenBase
from app.sections import Section

from .cc_consumption_controller import CCConsumptionController

from domain.cc_consumption import (
    get_model_gabinetes,
    get_vcc_nominal,
    get_vcc_for_currents,
    get_pct_global,
    get_usar_pct_global,
    get_num_escenarios,
    iter_cc_items,
    split_by_tipo,
)

import logging

log = logging.getLogger(__name__)


from screens.cc_consumption.widgets import (
    # columns
    PERM_COL_GAB, PERM_COL_TAG, PERM_COL_DESC, PERM_COL_PW, PERM_COL_PCT, PERM_COL_P_PERM, PERM_COL_I, PERM_COL_P_MOM, PERM_COL_I_OUT,
    MOM_COL_GAB, MOM_COL_TAG, MOM_COL_DESC, MOM_COL_PEFF, MOM_COL_I, MOM_COL_INCLUIR, MOM_COL_ESC,
    MOMR_COL_ESC, MOMR_COL_DESC, MOMR_COL_PT, MOMR_COL_IT,
    ALE_COL_SEL, ALE_COL_GAB, ALE_COL_TAG, ALE_COL_DESC, ALE_COL_PEFF, ALE_COL_I,
)

from .tabs.permanentes_tab import PermanentesTabMixin
from .tabs.momentaneos_tab import MomentaneosTabMixin
from .tabs.aleatorios_tab import AleatoriosTabMixin


class CCConsumptionScreen(ScreenBase, PermanentesTabMixin, MomentaneosTabMixin, AleatoriosTabMixin):
    SECTION = Section.CC
    porcentaje_util_changed = pyqtSignal(float)   # <-- nueva seÃ±al
    def __init__(self, data_model, parent=None):
        super().__init__(data_model, parent=parent)
        self.data_model = data_model
        self._controller = CCConsumptionController(data_model)
        self._building = False  # para no disparar seÃ±ales mientras se carga
        self._loading = False
        self._headers_restored = False

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

        # EventBus: refresh display on computed results.
        try:
            bus = getattr(self.data_model, "event_bus", None)
            if bus is not None:
                from app.events import Computed, ComputeStarted
                bus.subscribe(Computed, self._on_cc_computed)
                bus.subscribe(ComputeStarted, self._on_cc_compute_started)
        except Exception:
            log.debug("Failed to subscribe to Computed event (best-effort).", exc_info=True)

        # Startup-safe: do not compute totals during __init__. The orchestrator
        # will call reload_data() when a project is loaded or data changes.
        self.enter_safe_state()

    def enter_safe_state(self) -> None:
        """Put the screen in a safe empty state (no calculations, no dialogs)."""
        try:
            self._building = True
            # Clear tables to avoid showing stale data.
            tbl_mom = getattr(self, 'tbl_mom', None)
            if tbl_mom is not None:
                model = tbl_mom.model()
                if model is not None and hasattr(model, "set_items"):
                    model.set_items([])
            tbl_mom_res = getattr(self, 'tbl_mom_resumen', None)
            if tbl_mom_res is not None:
                model = tbl_mom_res.model()
                if model is not None and hasattr(model, 'set_rows'):
                    model.set_rows([])
            tbl_perm = getattr(self, 'tbl_perm', None)
            if tbl_perm is not None:
                model = tbl_perm.model()
                if model is not None and hasattr(model, "set_items"):
                    model.set_items([])
            tbl_ale = getattr(self, 'tbl_ale', None)
            if tbl_ale is not None:
                model = tbl_ale.model()
                if model is not None and hasattr(model, "set_items"):
                    model.set_items([])
            # Show a non-blocking hint.
            if hasattr(self, 'lbl_empty_hint'):
                self.lbl_empty_hint.setVisible(True)
        finally:
            self._building = False

    def _restore_ui_state(self):
        """Restore per-user UI state (safe)."""
        if self._headers_restored:
            return
        restored = False
        try:
            mapping = (
                (getattr(self, "tbl_perm", None), "cc.permanentes.header"),
                (getattr(self, "tbl_mom", None), "cc.momentaneos.header"),
                (getattr(self, "tbl_ale", None), "cc.aleatorios.header"),
                (getattr(self, "tbl_mom_resumen", None), "cc.escenarios.header"),
            )
            for table, key in mapping:
                if table is None or table.model() is None:
                    continue
                restore_header_state(table.horizontalHeader(), key)
                restored = True
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
        self._headers_restored = restored

    def _persist_ui_state(self):
        """Persist per-user UI state (safe)."""
        try:
            mapping = (
                (getattr(self, "tbl_perm", None), "cc.permanentes.header"),
                (getattr(self, "tbl_mom", None), "cc.momentaneos.header"),
                (getattr(self, "tbl_ale", None), "cc.aleatorios.header"),
                (getattr(self, "tbl_mom_resumen", None), "cc.escenarios.header"),
            )
            for table, key in mapping:
                if table is not None:
                    save_header_state(table.horizontalHeader(), key)
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def showEvent(self, event):
        """Al mostrar la pantalla, refrescar automÃ¡ticamente."""
        super().showEvent(event)
        self._emit_cc_input_changed(reason="show")

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
        if not hasattr(table, "item"):
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

        # Compute hint (non-blocking)
        self.lbl_cc_computing = QLabel("Calculando…")
        self.lbl_cc_computing.setProperty("mutedHint", True)
        self.lbl_cc_computing.setVisible(False)
        root.addWidget(self.lbl_cc_computing)

        # Widget de pestaÃ±as internas
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        # ================== Sección 1: Permanentes ==================
        self.grp_perm = QGroupBox("Consumos Permanentes en C.C.")
        g_perm = self.grp_perm
        v_perm = QVBoxLayout(g_perm)

        # LÃ­nea de tensiÃ³n nominal y % utilizaciÃ³n
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

        # (Auto-refresh) Eliminamos el botÃ³n "Actualizar datos". La vista se
        # actualiza automÃ¡ticamente al cambiar parÃ¡metros o al mostrar la pestaÃ±a.

        top_perm.addStretch()
        v_perm.addLayout(top_perm)
        # Tabla de permanentes
        self.tbl_perm = QTableView(self)
        configure_table_autoresize(self.tbl_perm)
        self.tbl_perm.verticalHeader().setDefaultSectionSize(26)
        self.tbl_perm.setSortingEnabled(True)

        # La tabla debe ocupar el alto disponible (ev el alto disponible (evita âaireâ debajo)
        v_perm.addWidget(self.tbl_perm, 1)

        # Totales y botÃ³n imagen
        bottom_perm = QHBoxLayout()

        self.lbl_perm_total_p_total = QLabel("Total P total: 0.00 [W]")
        self.lbl_perm_total_p_perm = QLabel("Total P permanente: 0.00 [W]")
        self.lbl_perm_total_i = QLabel("Total I permanente: 0.00 [A]")
        self.lbl_perm_total_p_mom = QLabel("Total P momentÃ¡nea: 0.00 [W]")
        self.lbl_perm_total_i_fuera = QLabel("Total I momentÃ¡nea: 0.00 [A]")

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
        # Tabla de cargas momentÃ¡neas
        self.tbl_mom = QTableView(self)
        configure_table_autoresize(self.tbl_mom)
        self.tbl_mom.verticalHeader().setDefaultSectionSize(26)
        self.tbl_mom.setSortingEnabled(True)

        # Tabla principal ocupa el alto disponible
        v_mom.addWidget(self.tbl_mom, 3)

        # Tabla de resumen por escenario (con descripcion)
        self.tbl_mom_resumen = QTableView(self)
        configure_table_autoresize(self.tbl_mom_resumen)
        self.tbl_mom_resumen.setSortingEnabled(True)
        self.tbl_mom_resumen.setEditTriggers(QAbstractItemView.AllEditTriggers)
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
        self.tbl_ale = QTableView(self)
        configure_table_autoresize(self.tbl_ale)
        self.tbl_ale.setSortingEnabled(True)
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
        # (auto-refresh) ya no hay botÃ³n manual.
        self.spin_pct_global.valueChanged.connect(self._on_global_pct_changed)
        self.chk_usar_global.toggled.connect(self._on_chk_usar_global_toggled)

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


    def refresh_metadata(self, fields=None):
        # Metadata changes should not trigger reload/recalc.
        self.refresh_display_only()

    def refresh_input(self, fields=None):
        # Display-only refresh driven by computed results.
        self.refresh_display_only()

    def refresh_display_only(self):
        if getattr(self, "_loading", False):
            return
        try:
            self.commit_pending_edits()
        except Exception:
            pass
        self._update_permanent_totals()
        self._update_momentary_summary_display()
        self._update_aleatory_totals()

    def _on_cc_computed(self, event):
        try:
            from app.sections import Section
            if getattr(event, "section", None) != Section.CC:
                return
            if hasattr(self, "lbl_cc_computing"):
                self.lbl_cc_computing.setVisible(False)
            self.refresh_display_only()
        except Exception:
            log.debug("Computed event handling failed (best-effort).", exc_info=True)

    def _emit_cc_input_changed(self, reason: str):
        bus = getattr(self.data_model, "event_bus", None)
        if bus is None:
            return
        try:
            from app.events import InputChanged
            bus.emit(InputChanged(section=Section.CC, fields={"reason": reason}))
        except Exception:
            log.debug("Failed to emit InputChanged (best-effort).", exc_info=True)

    def _on_cc_compute_started(self, event):
        try:
            from app.sections import Section
            if getattr(event, "section", None) != Section.CC:
                return
            if hasattr(self, "lbl_cc_computing"):
                self.lbl_cc_computing.setVisible(True)
        except Exception:
            log.debug("ComputeStarted handling failed (best-effort).", exc_info=True)


    # =========================================================
    # Helpers numÃ©ricos / de datos
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

    def load_from_model(self):
        # ScreenBase hook: cargar datos desde el modelo a la UI
        self.reload_data()

    def refresh_from_model(self):
        self.reload_data()

    def save_to_model(self):
        # ScreenBase hook: persistir ediciones pendientes al modelo
        self.commit_pending_edits()
        self._persist_ui_state()

    def reload_data(self):
        self.commit_pending_edits()
        self._building = True
        self._loading = True

        try:
            if hasattr(self.data_model, "ensure_aliases_consistent"):
                self.data_model.ensure_aliases_consistent()
        except Exception:
            log.debug("Failed to ensure aliases consistency (best-effort).", exc_info=True)

        # --- Proyecto / modelo ---
        proj = getattr(self.data_model, "proyecto", {}) or {}
        try:
            n_esc = int(proj.get("cc_num_escenarios", 1) or 1)
        except Exception:
            n_esc = 1
        try:
            self._controller.normalize_cc_scenarios_storage(n_esc)
        except Exception:
            log.debug("Failed to normalize cc scenarios (best-effort).", exc_info=True)
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
            tbl_perm = getattr(self, 'tbl_perm', None)
            if tbl_perm is not None:
                model = tbl_perm.model()
                if model is not None and hasattr(model, "set_items"):
                    model.set_items([])
            tbl_mom = getattr(self, 'tbl_mom', None)
            if tbl_mom is not None:
                model = tbl_mom.model()
                if model is not None and hasattr(model, "set_items"):
                    model.set_items([])
            tbl_mom_res = getattr(self, 'tbl_mom_resumen', None)
            if tbl_mom_res is not None:
                model = tbl_mom_res.model()
                if model is not None and hasattr(model, 'set_rows'):
                    model.set_rows([])
            tbl_ale = getattr(self, 'tbl_ale', None)
            if tbl_ale is not None:
                model = tbl_ale.model()
                if model is not None and hasattr(model, "set_items"):
                    model.set_items([])
            self._building = False
            self._loading = False
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

        if not all_items:
            try:
                gab_count = len(gabinetes or [])
                comp_count = 0
                example_data = None
                tipo_counts = {}
                for gab in gabinetes or []:
                    comps = gab.get("components", []) or []
                    comp_count += len(comps)
                    if example_data is None:
                        for comp in comps:
                            data = comp.get("data", None)
                            if isinstance(data, dict) and data:
                                example_data = {
                                    "tipo_consumo": data.get("tipo_consumo"),
                                    "potencia_w": data.get("potencia_w"),
                                }
                                break
                    for comp in comps:
                        data = comp.get("data", {}) or {}
                        tipo = str(data.get("tipo_consumo", "") or "")
                        if tipo:
                            tipo_counts[tipo] = tipo_counts.get(tipo, 0) + 1
                    if example_data is not None:
                        break
                log.debug(
                    "CC reload_data empty: gabinetes=%s components=%s example_data=%s",
                    gab_count,
                    comp_count,
                    example_data,
                )
                if comp_count > 0:
                    log.warning(
                        "CC reload_data empty but components exist: gabinetes=%s components=%s tipos=%s",
                        gab_count,
                        comp_count,
                        tipo_counts,
                    )
            except Exception:
                log.debug("CC reload_data empty: diagnostics failed.", exc_info=True)

        # --- Cargar tablas ---
        self._load_permanentes(permanentes, proj)            # <-- cambiado
        self._load_momentaneos(momentaneos) # <-- igual, pero ahora recibe CCItem
        self._load_aleatorios(aleatorios)                    # <-- igual, pero ahora recibe CCItem

        self._building = False
        self._loading = False
        self._restore_ui_state()

        # --- Render from current computed results (if any) ---
        self._rebuild_momentary_scenarios()
        self.refresh_display_only()
        self._apply_debug_tooltips()

        # Trigger compute via EventBus (debounced orchestrator).
        self._emit_cc_input_changed(reason="reload")

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

    def _on_global_pct_changed(self, value: float):
        if getattr(self, "_building", False):
            return
        try:
            # Persist input via controller (emits InputChanged(CC))
            self._controller.set_pct_global(float(value))
            if hasattr(self.data_model, "mark_dirty"):
                self.data_model.mark_dirty(True)
            # If global mode is active, update UI-only state
            if getattr(self, "chk_usar_global", None) is not None and self.chk_usar_global.isChecked():
                try:
                    self._apply_global_pct_mode()
                except Exception:
                    pass
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Failed to handle global pct change")

    def commit_pending_edits(self):
        """Solo fuerza commit del editor activo (NO recalcula ni llama totales)."""
        self._commit_table_edits()

    def _commit_table_edits(self):
        """
        Fuerza commit REAL de cualquier celda en ediciÃ³n.
        Sin esto, el texto puede quedar en el editor y NO en el QTableWidgetItem,
        por lo que al guardar se va el valor antiguo.
        """
        from PyQt5.QtWidgets import QApplication, QAbstractItemDelegate, QAbstractItemView

        app = QApplication.instance()

        for tbl in (
            getattr(self, "tbl_perm", None),
            getattr(self, "tbl_mom", None),
            getattr(self, "tbl_mom_resumen", None),  # â OJO: este es el nombre correcto
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
        Captura una secciÃ³n completa (el QGroupBox 'container'),
        expandiendo antes la tabla 'table' para que se vea completa.
        """
        if container is None or table is None:
            return

        tab_text = ""
        try:
            idx = self.tabs.currentIndex()
            tab_text = self.tabs.tabText(idx)
        except Exception:
            tab_text = ""

        tab_slug = (
            str(tab_text or "")
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace("ñ", "n")
        )
        base = str(default_name or "tabla").strip()
        if base.lower().endswith(".png"):
            base = base[:-4]
        if tab_slug and tab_slug not in base:
            base = f"{base}_{tab_slug}"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested_name = f"{base}_{stamp}.png"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar secciÃ³n como imagen",
            suggested_name,
            "PNG (*.png)"
        )
        if not path:
            return

        # Ajuste temporal de columnas para reducir riesgo de recortes en export.
        if hasattr(table, "columnCount"):
            col_count = table.columnCount()
        else:
            model = table.model()
            col_count = model.columnCount() if model is not None else 0
        original_col_widths = [table.columnWidth(col) for col in range(col_count)]
        try:
            table.resizeColumnsToContents()
            for col in range(col_count):
                w = table.columnWidth(col)
                if w > 420:
                    table.setColumnWidth(col, 420)
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        # ---------- 1) TamaÃ±o total de la tabla (todas las filas/columnas) ----------
        vh = table.verticalHeader()
        hh = table.horizontalHeader()
        frame = table.frameWidth() * 2

        width_table = vh.width() + frame
        for col in range(col_count):
            width_table += table.columnWidth(col)

        height_table = hh.height() + frame
        if hasattr(table, "rowCount"):
            row_count = table.rowCount()
        else:
            model = table.model()
            row_count = model.rowCount() if model is not None else 0
        for row in range(row_count):
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

        # Copiar tambiÃ©n al portapapeles
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
        for col, width in enumerate(original_col_widths):
            table.setColumnWidth(col, width)

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
