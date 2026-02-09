# -*- coding: utf-8 -*-
"""Application UI controller.

Centralizes creation of the main window, tabs (screens) and menu actions.
This keeps main.py as a thin entrypoint and reduces coupling to UI composition.

NOTE: This module intentionally contains PyQt5 imports and screen wiring.
"""
from __future__ import annotations


import json
import logging
import os
from pathlib import Path

from app.sections import Section
from PyQt5.QtWidgets import (
    QTabWidget, QMessageBox, QMainWindow, QAction, QActionGroup, QFileDialog,
    QProgressDialog, QApplication, QWidget, QHBoxLayout, QFrame, QTableWidget,
)
from PyQt5.QtCore import pyqtSignal, QTimer
from PyQt5.QtCore import Qt

from app.version import __version__ as APP_VERSION
from data_model import DataModel
from services.calc_service import CalcService
from services.validation_service import ValidationService
from services.section_orchestrator import SectionOrchestrator
from services.compute.qt_compute_orchestrator import QtComputeOrchestrator
from app.events import EventBus
from screens.project.main_screen import MainScreen
from screens.project.location_screen import LocationScreen
from screens.project.component_database_screen import ComponentDatabaseScreen
from screens.materials.materials_database_screen import MaterialsDatabaseScreen
from screens.common.help_window import HelpWindow
from screens.common.library_manager_window import LibraryManagerWindow
from ui.safe_widgets import ComboWheelFilter
from screens.cabinet.cabinet_screen import CabinetComponentsScreen
from screens.board_feed.board_feed_screen import BoardFeedScreen
from screens.load_tables.load_tables_screen import LoadTablesScreen
from screens.ssaa_designer.ssaa_designer_screen import SSAADesignerScreen
from screens.cc_consumption.cc_consumption_screen import CCConsumptionScreen
from screens.bank_charger.bank_charger_screen import BankChargerSizingScreen
from ui.common.state import (
    get_ui_theme,
    set_ui_theme,
    get_nav_mode as get_saved_nav_mode,
    set_nav_mode as save_nav_mode,
)
from ui.common.ui_roles import set_role_form, auto_tag_tables
from ui.theme import apply_named_theme
from ui.widgets.sidebar import Sidebar

# Guardrails / ownership catalog (kept in app layer to avoid UI cross-coupling)
from app.section_catalog import validate_catalog

BASE_DIR = Path(__file__).resolve().parent.parent
log = logging.getLogger(__name__)

class BatteryBankCalculatorApp(QTabWidget):
    project_loaded = pyqtSignal(str)
    refresh_finished = pyqtSignal()
    def __init__(self, data_model=None):
        """Contenedor principal de pestañas.

        Si se provee `data_model`, se utiliza como fuente única de verdad para
        todo el proyecto. Si no se provee, se crea uno nuevo.
        """
        super().__init__()
        self.data_model = data_model if data_model is not None else DataModel()
        self.event_bus = EventBus()
        setattr(self.data_model, "event_bus", self.event_bus)

        # Services (no UI dependencies)
        self.calc_service = CalcService(self.data_model)
        # Expose for screens that want to call it without importing the controller.
        # This keeps the dependency direction: UI -> DataModel(+services), not UI -> controller.
        setattr(self.data_model, "calc_service", self.calc_service)

        # Validation + orchestration (no UI dependencies)
        self.validation_service = ValidationService(self.data_model)
        setattr(self.data_model, "validation_service", self.validation_service)

        self.section_orchestrator = SectionOrchestrator(
            app=self,
            data_model=self.data_model,
            calc_service=self.calc_service,
            validation_service=self.validation_service,
            event_bus=self.event_bus,
        )
        # Compute orchestrator (debounced auto-recalc, no UI coupling)
        try:
            self.compute_orchestrator = QtComputeOrchestrator(
                event_bus=self.event_bus,
                data_model=self.data_model,
                debounce_ms=200,
            )
            setattr(self.data_model, "compute_orchestrator", self.compute_orchestrator)
        except Exception:
            self.compute_orchestrator = None
        # Subscribe to model-level events (observer pattern)
        if hasattr(self.data_model, "on"):
            self.data_model.on("section_changed", self._on_section_changed)
            self.data_model.on("section_viewed", self._on_section_viewed)
            self.data_model.on("project_loaded", lambda _p: self._on_project_loaded_event())
        self.initUI()
        self.project_loaded.connect(self._handle_project_loaded)
        self.setWindowTitle(f"Calculadora SS/AA {APP_VERSION}")
        # Tamaño mínimo cómodo, pero la ventana puede crecer libremente
        self.setMinimumSize(1200, 800)

    def initUI(self):
        self.main_screen = MainScreen(self.data_model)
        self.location_screen = LocationScreen(self.data_model)
        # Definición de necesidades de alimentación (qué requiere cada carga)
        self.board_feed_screen = BoardFeedScreen(self.data_model)
        self.load_tables_screen = LoadTablesScreen(self.data_model)
        self.ssaa_designer_screen = SSAADesignerScreen(self.data_model)
        self.cabinet_screen = CabinetComponentsScreen(self.data_model)
        self.cc_screen = CCConsumptionScreen(self.data_model)
        self.bank_screen = BankChargerSizingScreen(self.data_model)

        # 🔄 Sincronizar % de utilización en ambos sentidos
        self.main_screen.porcentaje_util_changed.connect(
            self.cc_screen.set_pct_from_outside
        )
        self.cc_screen.porcentaje_util_changed.connect(
            self.main_screen.set_pct_from_outside
        )

        # Además: propagar como evento lógico para recalcular/validar/refrescar
        try:
            self.main_screen.porcentaje_util_changed.connect(lambda *_: self.data_model.notify_section_changed(Section.CC))
        except Exception:
            pass
        try:
            self.cc_screen.porcentaje_util_changed.connect(lambda *_: self.data_model.notify_section_changed(Section.CC))
        except Exception:
            pass
        self.currentChanged.connect(self._on_tab_changed)
        self.addTab(self.main_screen, "Proyecto")
        self.addTab(self.location_screen, "Instalaciones")
        self.addTab(self.cabinet_screen, "Consumos (gabinetes)")
        self.addTab(self.cc_screen, "Consumos C.C.")
        self.addTab(self.bank_screen, "Banco y cargador")
        self.addTab(self.board_feed_screen, "Alimentación tableros")
        self.addTab(self.ssaa_designer_screen, "Arquitectura SS/AA")
        self.addTab(self.load_tables_screen, "Cuadros de carga")

        # Guardrail: ensure required screens are present (debug only raises)
        validate_catalog(self)

        # Propagación de cambios por "secciones" (declarativo via SectionOrchestrator)
        try:
            self.location_screen.cabinets_updated.connect(lambda *_: self.data_model.notify_section_changed(Section.INSTALACIONES))
        except Exception:
            pass
        try:
            self.cabinet_screen.data_changed.connect(lambda *_: self.data_model.notify_section_changed(Section.CABINET))
        except Exception:
            pass

    # ---------------- DataModel event handlers ----------------
    def _on_section_changed(self, section):
        """React to logical section changes (from any screen)."""
        try:
            self.section_orchestrator.on_section_changed(section)
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def _on_project_loaded_event(self):
        """When project is loaded by storage.project_io (fallback paths)."""
        try:
            self.section_orchestrator.on_project_loaded()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def _handle_project_loaded(self, project_path: str):
        """Hook único post-carga de proyecto.

        - Recarga automáticamente librerías asociadas al proyecto (consumos/materiales),
          resolviendo rutas relativas contra la carpeta del proyecto.
        - Refresca pantallas dependientes sin abrir diálogos ni marcar el proyecto como modificado.
        """
        dm = self.data_model

        if hasattr(dm, "set_ui_refreshing"):
            dm.set_ui_refreshing(True)
        try:
            links = getattr(dm, "library_paths", {}) or {}

            for kind in ("consumos", "materiales"):
                lib_path = (links.get(kind) or "").strip()
                if not lib_path:
                    continue
                try:
                    dm.load_library(kind, lib_path)
                except Exception as e:
                    print(f"[WARN] No se pudo cargar librería '{kind}': {e}")

            # Refrescar pantallas dependientes usando el grafo de dependencias
            # (sin diálogos y sin marcar dirty).
            try:
                self.section_orchestrator.on_project_loaded()
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

            # Kick CC compute after load via EventBus.
            try:
                from app.events import InputChanged
                self.event_bus.emit(InputChanged(section=Section.CC, fields={"reason": "project_loaded"}))
            except Exception:
                import logging
                logging.getLogger(__name__).debug('compute trigger failed', exc_info=True)

            # Mantener estado limpio tras carga (no debe marcar dirty por refrescos UI)
            dm.mark_dirty(False)
        finally:
            if hasattr(dm, "set_ui_refreshing"):
                dm.set_ui_refreshing(False)

    def _on_section_viewed(self, section):
        """React to view activations (tab changes).

        Root-cause performance policy:
        - Switching tabs must not trigger heavy recalculation.
        - Only refresh the visible UI from the current model snapshot.
        """
        try:
            self.section_orchestrator.on_section_viewed(section)
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)


    def _refresh_after_project_load(self):
        """Refresh UI after a project is loaded.

        IMPORTANT: do not directly refresh screens here; delegate to the
        SectionOrchestrator via the declarative SECTION_GRAPH. This avoids
        cross-screen hydra wiring and keeps the controller thin.
        """
        dm = getattr(self, "data_model", None)
        if dm and hasattr(dm, "set_ui_refreshing"):
            dm.set_ui_refreshing(True)
        try:
            # Single source of truth: orchestrator decides what to recalc/validate/refresh
            try:
                self.section_orchestrator.on_project_loaded()
            except Exception:
                import logging
                logging.getLogger(__name__).debug("orchestrator.on_project_loaded failed", exc_info=True)
        finally:
            if dm and hasattr(dm, "set_ui_refreshing"):
                dm.set_ui_refreshing(False)

    def _on_tab_changed(self, index: int):
        # 1) Forzar commit de ediciones pendientes (tab actual si es posible).
        try:
            current = self.currentWidget()
            if current is not None and hasattr(current, "commit_pending_edits"):
                current.commit_pending_edits()
            elif hasattr(self, "commit_pending_edits"):
                self.commit_pending_edits()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)


        widget = self.widget(index)

        # ✅ Root-cause fix: never refresh screens directly here.
        # Tab changes should go through the orchestrator using a declared Section.
        dm = getattr(self, "data_model", None)
        section = getattr(widget, "SECTION", None)
        if dm is not None and section is not None and hasattr(dm, "notify_section_viewed"):
            try:
                dm.notify_section_viewed(section)
                return
            except Exception:
                import logging
                logging.getLogger(__name__).debug("notify_section_viewed failed", exc_info=True)

        # Fallback (legacy widgets without SECTION): call their own refresh hook only.
        if hasattr(widget, "refresh_from_model"):
            try:
                widget.refresh_from_model()
            except Exception:
                import logging
                logging.getLogger(__name__).debug("refresh_from_model failed", exc_info=True)

    def set_debug_mode(self, enabled: bool):
        for w in (
            getattr(self, "cc_screen", None),
            getattr(self, "cabinet_screen", None),
            
            getattr(self, "bank_screen", None),
        ):
            if w is not None and hasattr(w, "set_debug_mode"):
                w.set_debug_mode(enabled)

    def actualizar_pantallas(self):
        """Legacy action kept for compatibility.

        Root-cause approach: do NOT manually refresh each screen here.
        Delegate to the orchestrator (single source of truth).
        """
        dm = getattr(self, "data_model", None)
        try:
            if dm is not None and hasattr(dm, "set_ui_refreshing"):
                dm.set_ui_refreshing(True)
            orch = getattr(self, "section_orchestrator", None)
            if orch is not None and hasattr(orch, "on_project_loaded"):
                orch.on_project_loaded()
            else:
                raise RuntimeError("SectionOrchestrator no disponible")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al actualizar pantallas: {str(e)}")
        finally:
            if dm is not None and hasattr(dm, "set_ui_refreshing"):
                dm.set_ui_refreshing(False)
            try:
                self.refresh_finished.emit()
            except Exception:
                pass

    def commit_pending_edits(self):
        """Fuerza commit de ediciones pendientes en pestañas que lo soporten."""
        for w in (getattr(self, 'cabinet_screen', None), getattr(self, 'cc_screen', None), getattr(self, 'bank_screen', None)):
            if w is not None and hasattr(w, 'commit_pending_edits'):
                try:
                    w.commit_pending_edits()
                except Exception:
                    import logging
                    logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Calculadora SS/AA {APP_VERSION} – alfa")
        self.setGeometry(200, 100, 1200, 800)

        self.data_model = DataModel()

        # Durante el armado inicial de la UI se disparan varias señales
        # (setText, setCurrentIndex, recálculos, etc.). Estas NO deben
        # marcar el proyecto como con cambios.
        self.data_model.set_ui_refreshing(True)

        # Widget principal con tabs
        self.app_widget = BatteryBankCalculatorApp(self.data_model)
        self.sidebar = Sidebar()
        self.sidebar.navigate_requested.connect(self._on_sidebar_navigate)

        self._central = QWidget()
        lay = QHBoxLayout(self._central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.sidebar)
        lay.addWidget(self.app_widget, 1)
        self.setCentralWidget(self._central)
        set_role_form(self.app_widget)
        auto_tag_tables(self.app_widget)
        self.app_widget.currentChanged.connect(self._on_tab_changed_for_sidebar)

        # Fin del armado inicial
        self.data_model.set_ui_refreshing(False)
        self.data_model.mark_dirty(False)

        self._create_menus()
        self.set_nav_mode(get_saved_nav_mode())
        QTimer.singleShot(0, self._sync_sidebar_initial_state)

        # Ventanas flotantes (reutilizables)
        self._lib_manager = None
        self._db_consumos = None
        self._db_materiales = None

    def _sync_sidebar_initial_state(self) -> None:
        """Asegura estilo/seleccion correctos de sidebar al arranque."""
        try:
            if hasattr(self, "app_widget") and hasattr(self, "sidebar"):
                idx = int(self.app_widget.currentIndex())
                if hasattr(self.sidebar, "set_active"):
                    self.sidebar.set_active(idx)

            for w in (self, getattr(self, "sidebar", None), getattr(self, "app_widget", None)):
                if w is None:
                    continue
                w.style().unpolish(w)
                w.style().polish(w)
                w.update()
        except Exception:
            pass

    def _on_sidebar_navigate(self, tab_index: int) -> None:
        try:
            self.app_widget.setCurrentIndex(int(tab_index))
        except Exception:
            pass

    def _on_tab_changed_for_sidebar(self, index: int) -> None:
        try:
            self.sidebar.set_active(int(index))
        except Exception:
            pass

    def set_nav_mode(self, mode: str) -> None:
        mode = (mode or "classic").strip().lower()
        if mode not in ("classic", "modern"):
            mode = "classic"

        self._nav_mode = mode
        save_nav_mode(mode)

        if mode == "classic":
            self.sidebar.hide()
            self.app_widget.tabBar().show()
        else:
            self.sidebar.show()
            self.app_widget.tabBar().hide()
            self.sidebar.set_active(self.app_widget.currentIndex())
        self._apply_ui_mode_properties(mode)

    def _apply_ui_mode_properties(self, mode: str) -> None:
        is_modern = mode == "modern"
        self.setProperty("glass", is_modern)
        self.setProperty("ui_mode", mode)
        self.app_widget.setProperty("glass", is_modern)
        self.app_widget.setProperty("ui_mode", mode)
        auto_tag_tables(self.app_widget)
        for t in self.app_widget.findChildren(QTabWidget):
            t.setProperty("glass", is_modern)
        for table in self.app_widget.findChildren(QTableWidget):
            table.setProperty("glass", is_modern)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    # ---------------------------------------------------------
    # Menús / acciones
    # ---------------------------------------------------------
    def _create_menus(self):
        menubar = self.menuBar()

        # Archivo
        file_menu = menubar.addMenu("Archivo")

        act_open = QAction("Abrir proyecto…", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self.open_project_from_menu)
        file_menu.addAction(act_open)

        act_save = QAction("Guardar proyecto", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self.save_project_from_menu)
        file_menu.addAction(act_save)

        act_save_as = QAction("Guardar proyecto como…", self)
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(self.save_as_project_from_menu)
        file_menu.addAction(act_save_as)

        file_menu.addSeparator()

        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Herramientas
        tools_menu = menubar.addMenu("Herramientas")
        db_action = QAction("Librería de consumos…", self)
        db_action.triggered.connect(self.open_component_database)
        tools_menu.addAction(db_action)

        db_mat_action = QAction("Librería de materiales…", self)
        db_mat_action.triggered.connect(self.open_materials_database)
        tools_menu.addAction(db_mat_action)

        lib_action = QAction("Gestor de librerías…", self)
        lib_action.setShortcut("Ctrl+L")
        lib_action.triggered.connect(self.open_library_manager)
        tools_menu.addAction(lib_action)

        # Ver
        view_menu = menubar.addMenu("Ver")
        theme_menu = view_menu.addMenu("Tema")

        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        act_theme_light = QAction("Claro", self, checkable=True)
        act_theme_dark = QAction("Oscuro", self, checkable=True)
        theme_group.addAction(act_theme_light)
        theme_group.addAction(act_theme_dark)
        theme_menu.addAction(act_theme_light)
        theme_menu.addAction(act_theme_dark)

        current_theme = get_ui_theme()
        if current_theme == "dark":
            act_theme_dark.setChecked(True)
        else:
            act_theme_light.setChecked(True)

        act_theme_light.triggered.connect(lambda: self._apply_ui_theme("light"))
        act_theme_dark.triggered.connect(lambda: self._apply_ui_theme("dark"))

        nav_menu = view_menu.addMenu("Navegacion")
        nav_group = QActionGroup(self)
        nav_group.setExclusive(True)

        act_nav_classic = QAction("Modo clasico", self, checkable=True)
        act_nav_modern = QAction("Modo moderno", self, checkable=True)
        nav_group.addAction(act_nav_classic)
        nav_group.addAction(act_nav_modern)
        nav_menu.addAction(act_nav_classic)
        nav_menu.addAction(act_nav_modern)

        nav_mode = get_saved_nav_mode()
        if nav_mode == "modern":
            act_nav_modern.setChecked(True)
        else:
            act_nav_classic.setChecked(True)

        act_nav_classic.triggered.connect(lambda: self.set_nav_mode("classic"))
        act_nav_modern.triggered.connect(lambda: self.set_nav_mode("modern"))

        # Ayuda
        help_menu = menubar.addMenu("Ayuda")
        help_action = QAction("Acerca de", self)
        help_action.triggered.connect(self.open_help)
        help_menu.addAction(help_action)

        # Debug (opcional)
        debug_menu = menubar.addMenu("Debug")
        debug_action = QAction("Activar modo debug", self, checkable=True)
        debug_action.triggered.connect(self.toggle_debug_mode)
        debug_menu.addAction(debug_action)

    def _apply_ui_theme(self, theme_name: str) -> None:
        try:
            set_ui_theme(theme_name)
            apply_named_theme(QApplication.instance(), theme_name)
        except Exception:
            log.debug("Failed to apply UI theme '%s'", theme_name, exc_info=True)

    def toggle_debug_mode(self, checked):
        # Activa/desactiva etiquetas debug en la pantalla de Arquitectura SS/AA
        ssaa_screen = self.app_widget.ssaa_designer_screen
        ssaa_screen.set_debug_mode(bool(checked))
    def open_help(self):
        QMessageBox.information(
            self,
            "Acerca de",
            "Calculadora de Bancos de Baterías (alfa)\n\nHerramienta de apoyo para diseño de SS/AA.",
        )


    # ---------------------------------------------------------
    # Abrir / guardar
    # ---------------------------------------------------------
    def _maybe_prompt_save_if_dirty(self) -> bool:
        """Retorna True si se puede continuar (sin cancelar)."""
        dm = self.data_model
        if not getattr(dm, "dirty", False):
            return True

        reply = QMessageBox.question(
            self,
            "Cambios sin guardar",
            "Hay cambios sin guardar. ¿Deseas guardarlos antes de continuar?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Yes:
            self.save_project_from_menu()
            return not getattr(dm, "dirty", False)
        return True

    def open_project_from_menu(self):
        if not self._maybe_prompt_save_if_dirty():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir proyecto",
            "",
            "Proyecto SS/AA (*.ssaa *.json);;Todos los archivos (*.*)",
        )
        if not file_path:
            return

        # UX: mostrar feedback inmediato (antes de recálculos/refrescos).
        prog = QProgressDialog("Cargando proyecto…", "", 0, 0, self)
        prog.setWindowTitle("SS/AA")
        prog.setWindowModality(Qt.WindowModal)
        prog.setCancelButton(None)
        prog.setMinimumDuration(0)
        prog.show()
        QApplication.processEvents()

        try:
            self.data_model.load_from_file(file_path)
            self.app_widget.project_loaded.emit(file_path)

            prog.setLabelText("Actualizando pantallas…")
            QApplication.processEvents()

            # Close the progress dialog when the orchestrated refresh finishes.
            def _close_prog():
                try:
                    self.app_widget.refresh_finished.disconnect(_close_prog)
                except Exception:
                    pass
                prog.close()

            try:
                self.app_widget.refresh_finished.connect(_close_prog)
            except Exception:
                pass

            # Defer refresh to the next event loop tick so the dialog paints.
            QTimer.singleShot(0, self.app_widget.actualizar_pantallas)
        except Exception as e:
            prog.close()
            QMessageBox.critical(self, "Error", f"No se pudo abrir el proyecto:\n\n{e}")
            return

        # If anything goes wrong and the signal never fires, don't leave a stuck dialog.
        QTimer.singleShot(15000, prog.close)

    def save_project_from_menu(self):
        """Guardar (Ctrl+S). Si no hay archivo asociado, actúa como Guardar como…"""
        dm = self.data_model
        self.app_widget.commit_pending_edits()

        if not getattr(dm, "file_path", None):
            self.save_as_project_from_menu()
            return

        try:
            dm.save_to_file()  # usa dm.file_path actual
            QMessageBox.information(self, "Guardar proyecto", "Proyecto guardado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el proyecto:\n\n{e}")

    def save_as_project_from_menu(self):
        dm = self.data_model
        self.app_widget.commit_pending_edits()

        default_name = getattr(dm, "project_filename", "") or "proyecto_ssaa.ssaa"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar proyecto como",
            default_name,
            "Proyecto SS/AA (*.ssaa)",
        )
        if not file_path:
            return

        if not file_path.lower().endswith(".ssaa"):
            file_path += ".ssaa"

        try:
            dm.save_to_file(file_path)
            QMessageBox.information(self, "Guardar proyecto", "Proyecto guardado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el proyecto:\n\n{e}")

    def open_component_database(self):
        # Reutilizar ventana y forzar modalidad (evita múltiples instancias)
        if self._db_consumos is None:
            self._db_consumos = ComponentDatabaseScreen(self.data_model, parent=self)
        # Ejecutar modal (bloquea el uso hasta cerrar)
        self._db_consumos.exec_()
        # refrescar pantallas para que catálogos se actualicen (p.ej. Consumos)
        self.app_widget.actualizar_pantallas()

    def open_materials_database(self):
        # Reutilizar ventana y forzar modalidad (evita múltiples instancias)
        if self._db_materiales is None:
            self._db_materiales = MaterialsDatabaseScreen(self.data_model, parent=self)
        self._db_materiales.exec_()
        # por ahora no hay pantallas que consuman materiales, pero mantenemos consistencia
        self.app_widget.actualizar_pantallas()

    def open_library_manager(self):
        # Reutilizar ventana para no crear múltiples instancias
        if self._lib_manager is None:
            self._lib_manager = LibraryManagerWindow(self.data_model, parent=self)
        self._lib_manager.show()
        self._lib_manager.raise_()
        self._lib_manager.activateWindow()

    # ---------------------------------------------------------
    # Cierre con control de cambios
    # ---------------------------------------------------------
    def closeEvent(self, event):
        dm = self.data_model
        if getattr(dm, "dirty", False):
            resp = QMessageBox.question(
                self,
                "Cambios sin guardar",
                "Tienes cambios sin guardar. ¿Deseas guardar antes de salir?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if resp == QMessageBox.Save:
                self.save_project_from_menu()
                if not getattr(dm, "dirty", False):
                    event.accept()
                else:
                    event.ignore()
                return
            if resp == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()


def create_main_window() -> MainWindow:
    """Factory used by main.py."""
    return MainWindow()
