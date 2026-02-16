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
    QUndoGroup, QDialog, QDialogButtonBox, QSpinBox, QLabel, QVBoxLayout,
)
from PyQt5.QtCore import pyqtSignal, QTimer, QSignalBlocker
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
    get_int,
    set_int,
)
from ui.common.recent_projects import RecentProjectsStore
from ui.common.refresh_coordinator import RefreshCoordinator
from ui.common.screen_state import restore_screen_state, persist_screen_state, iter_main_screens
from ui.common.ui_roles import set_role_form, auto_tag_tables, auto_tag_user_fields
from ui.theme import apply_named_theme
from ui.utils.style_utils import repolish_tree
from ui.widgets.sidebar import Sidebar
from app.dirty_tracker import DirtyTracker

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
        self._refresh_coordinator = None
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
        self.addTab(self.main_screen, "Proyecto")
        self.addTab(self.location_screen, "Instalaciones")
        self.addTab(self.cabinet_screen, "Consumos (gabinetes)")
        self.addTab(self.cc_screen, "Consumos C.C.")
        self.addTab(self.bank_screen, "Banco y cargador")
        self.addTab(self.board_feed_screen, "Alimentación tableros")
        self.addTab(self.ssaa_designer_screen, "Arquitectura SS/AA")
        self.addTab(self.load_tables_screen, "Cuadros de carga")
        self._prev_index = self.currentIndex()
        self.currentChanged.connect(self._on_tab_changed)

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

    def set_refresh_coordinator(self, coordinator) -> None:
        old = getattr(self, "_refresh_coordinator", None)
        if old is not None and old is not coordinator:
            try:
                old.refresh_finished.disconnect(self._on_coordinator_refresh_finished)
            except Exception:
                pass
        self._refresh_coordinator = coordinator
        if coordinator is not None:
            try:
                coordinator.refresh_finished.connect(self._on_coordinator_refresh_finished)
            except Exception:
                import logging
                logging.getLogger(__name__).debug("Failed to wire refresh coordinator.", exc_info=True)

    def _on_coordinator_refresh_finished(self, _reason: str = "") -> None:
        try:
            self.refresh_finished.emit()
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
            self._sync_after_project_loaded("")
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def _handle_project_loaded(self, project_path: str):
        """Hook post-carga para compatibilidad con emisores legacy."""
        self._sync_after_project_loaded(project_path)

    def _sync_after_project_loaded(self, project_path: str = "") -> None:
        _ = project_path
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
                except Exception:
                    import logging
                    logging.getLogger(__name__).debug("load_library failed (%s)", kind, exc_info=True)

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
        prev_index = getattr(self, "_prev_index", None)
        prev_widget = None
        try:
            if prev_index is not None and 0 <= int(prev_index) < self.count():
                prev_widget = self.widget(int(prev_index))
        except Exception:
            prev_widget = None

        # 1) Guardias: si la pantalla anterior no permite salir, revertimos
        # y cortamos sin side-effects.
        if (
            prev_widget is not None
            and prev_index is not None
            and int(prev_index) != int(index)
        ):
            try:
                checker = getattr(prev_widget, "can_deactivate", None)
                can_leave = True
                if callable(checker):
                    can_leave = bool(checker(self))
                if not can_leave:
                    blocker = QSignalBlocker(self)
                    try:
                        self.setCurrentIndex(int(prev_index))
                    finally:
                        del blocker
                    return
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        # 2) Commit de ediciones pendientes SOLO si el cambio fue permitido.
        try:
            if prev_widget is not None and hasattr(prev_widget, "commit_pending_edits"):
                prev_widget.commit_pending_edits()
            elif hasattr(self, "commit_pending_edits"):
                self.commit_pending_edits()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

        # 3) Activar vista y hacer refresh liviano de pantalla activa.
        try:
            real_index = int(self.currentIndex())
        except Exception:
            real_index = int(index)
        widget = None
        try:
            if 0 <= real_index < self.count():
                widget = self.widget(real_index)
        except Exception:
            widget = None

        coordinator = getattr(self, "_refresh_coordinator", None)
        if coordinator is not None and widget is not None:
            try:
                coordinator.refresh_active_only(widget, reason="tab_changed")
            except Exception:
                import logging
                logging.getLogger(__name__).debug("refresh_active_only failed", exc_info=True)
        elif widget is not None:
            try:
                hook = getattr(widget, "on_view_activated", None)
                if callable(hook):
                    hook(reason="tab_changed")
                elif hasattr(widget, "refresh_from_model"):
                    try:
                        widget.refresh_from_model(reason="tab_changed", force=False)
                    except TypeError:
                        widget.refresh_from_model()
            except Exception:
                import logging
                logging.getLogger(__name__).debug("tab activation refresh failed", exc_info=True)

        try:
            self._prev_index = int(real_index)
        except Exception:
            pass

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

        Prefer central RefreshCoordinator (batched + revision-aware).
        """
        coordinator = getattr(self, "_refresh_coordinator", None)
        if coordinator is not None:
            try:
                coordinator.request("refresh_all", force=True)
                return
            except Exception:
                import logging
                logging.getLogger(__name__).debug("RefreshCoordinator request failed", exc_info=True)

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
        for i in range(self.count()):
            try:
                w = self.widget(i)
                if w is not None and hasattr(w, "commit_pending_edits"):
                    w.commit_pending_edits()
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

class MainWindow(QMainWindow):
    KEY_LAST_MAIN_TAB = "ui/last_main_tab"

    def __init__(self):
        super().__init__()
        self._base_title = f"Calculadora SS/AA {APP_VERSION} – alfa"
        self.setGeometry(200, 100, 1200, 800)

        self.data_model = DataModel()
        self._dirty_tracker = DirtyTracker(initial_dirty=bool(getattr(self.data_model, "dirty", False)))
        self._recents = RecentProjectsStore()
        self._recent_menu = None
        try:
            if hasattr(self.data_model, "on"):
                self.data_model.on("project_loaded", self._on_dm_project_loaded)
                self.data_model.on("project_saved", self._on_dm_project_saved)
                self.data_model.on("dirty_changed", self._on_dm_dirty_changed)
        except Exception:
            log.debug("Failed to wire DataModel events (best-effort).", exc_info=True)

        # Durante el armado inicial de la UI se disparan varias señales
        # (setText, setCurrentIndex, recálculos, etc.). Estas NO deben
        # marcar el proyecto como con cambios.
        self.data_model.set_ui_refreshing(True)

        # Widget principal con tabs
        self.app_widget = BatteryBankCalculatorApp(self.data_model)
        self._refresh = RefreshCoordinator(
            self.data_model,
            screens_provider=lambda: list(iter_main_screens(self.app_widget)),
        )
        self.app_widget.set_refresh_coordinator(self._refresh)
        self.sidebar = Sidebar()
        self.sidebar.navigate_requested.connect(self._on_sidebar_navigate)
        self._last_tab_index = self.app_widget.currentIndex()
        self._last_tab_widget = self.app_widget.currentWidget()
        self._undo_group = QUndoGroup(self)
        self._register_screen_undo_stacks()

        self._central = QWidget()
        lay = QHBoxLayout(self._central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.sidebar)
        lay.addWidget(self.app_widget, 1)
        self.setCentralWidget(self._central)
        self._apply_ui_tags_and_repolish(self._central)
        self.app_widget.currentChanged.connect(self._on_tab_changed_for_sidebar)
        self.app_widget.currentChanged.connect(self._persist_last_main_tab)
        self.app_widget.currentChanged.connect(self._set_active_undo_stack)
        self.app_widget.refresh_finished.connect(self._on_refresh_finished_apply_ui)
        self.app_widget.refresh_finished.connect(self._after_refresh_restore_screen_states)

        # Fin del armado inicial
        self.data_model.set_ui_refreshing(False)
        self.data_model.mark_dirty(False)
        self._dirty_tracker.clear_dirty()

        self._create_menus()
        self.set_nav_mode(get_saved_nav_mode())
        QTimer.singleShot(0, self._restore_last_main_tab)
        QTimer.singleShot(0, self._sync_sidebar_initial_state)
        QTimer.singleShot(0, lambda: self._refresh.request("startup", force=True))
        QTimer.singleShot(0, lambda: self._set_active_undo_stack(self.app_widget.currentIndex()))
        self._update_window_title()

        # Ventanas flotantes (reutilizables)
        self._lib_manager = None
        self._db_consumos = None
        self._db_materiales = None
        self._proj_open_freeze_prev = None
        self._proj_open_in_progress = False
        try:
            app = QApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(self._persist_all_screen_states)
        except Exception:
            log.debug("Failed to wire global screen-state persistence hook.", exc_info=True)

    def _apply_ui_tags_and_repolish(self, root: QWidget) -> None:
        try:
            if root is None:
                return
            set_role_form(root)
            auto_tag_tables(root)
            auto_tag_user_fields(root)
            repolish_tree(root)
        except Exception:
            log.debug("Failed to apply UI tags/repolish (best-effort).", exc_info=True)

    def _begin_ui_freeze(self) -> None:
        try:
            if self._proj_open_freeze_prev is not None:
                return
            root = self._central if self._central is not None else self.app_widget
            if root is None:
                return
            snapshot = [(root, bool(root.isEnabled()), bool(root.updatesEnabled()))]
            try:
                root.setUpdatesEnabled(False)
                root.setEnabled(False)
            except Exception:
                pass
            self._proj_open_freeze_prev = snapshot
            try:
                QApplication.setOverrideCursor(Qt.WaitCursor)
            except Exception:
                pass
        except Exception:
            log.debug("Failed to begin UI freeze (best-effort).", exc_info=True)

    def _end_ui_freeze(self) -> None:
        try:
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass
            snapshot = self._proj_open_freeze_prev or []
            for widget, was_enabled, had_updates in snapshot:
                try:
                    widget.setEnabled(bool(was_enabled))
                except Exception:
                    pass
                try:
                    widget.setUpdatesEnabled(bool(had_updates))
                except Exception:
                    pass
            for widget in (self._central, self.app_widget):
                try:
                    if widget is not None:
                        widget.update()
                        widget.repaint()
                except Exception:
                    pass
            try:
                tb_fn = getattr(self.app_widget, "tabBar", None)
                if callable(tb_fn):
                    tb = tb_fn()
                    if tb is not None:
                        tb.update()
                        tb.repaint()
            except Exception:
                pass
        except Exception:
            log.debug("Failed to end UI freeze (best-effort).", exc_info=True)
        finally:
            self._proj_open_freeze_prev = None
            self._proj_open_in_progress = False

    def _push_recent(self, file_path: str) -> None:
        try:
            self._recents.push(file_path)
        except Exception:
            pass
        try:
            self._rebuild_recent_menu()
        except Exception:
            pass

    def _clear_recents(self) -> None:
        try:
            self._recents.clear()
        except Exception:
            pass
        try:
            self._rebuild_recent_menu()
        except Exception:
            pass

    def _rebuild_recent_menu(self) -> None:
        if self._recent_menu is None:
            return
        self._recent_menu.clear()

        try:
            paths = self._recents.list(existing_only=True, prune_missing=True)
        except Exception:
            paths = []

        if not paths:
            empty_action = QAction("(Sin recientes)", self)
            empty_action.setEnabled(False)
            self._recent_menu.addAction(empty_action)
            self._recent_menu.addSeparator()
            clear_action = QAction("Limpiar recientes", self)
            clear_action.setEnabled(False)
            self._recent_menu.addAction(clear_action)
            return

        for p in paths:
            text = f"{os.path.basename(p)} — {os.path.dirname(p)}"
            action = QAction(text, self)
            action.setToolTip(p)
            action.triggered.connect(lambda checked=False, path=p: self._open_recent_path(path))
            self._recent_menu.addAction(action)

        self._recent_menu.addSeparator()
        clear_action = QAction("Limpiar recientes", self)
        clear_action.triggered.connect(self._clear_recents)
        self._recent_menu.addAction(clear_action)

    def _open_recent_path(self, file_path: str) -> None:
        p = str(file_path or "").strip()
        if not p:
            return
        try:
            exists = os.path.exists(p)
        except Exception:
            exists = False
        if not exists:
            QMessageBox.warning(self, "Abrir reciente", "El archivo seleccionado ya no existe.")
            try:
                self._recents.remove(p)
            except Exception:
                pass
            self._rebuild_recent_menu()
            return
        if not self._maybe_prompt_save_if_dirty():
            return
        try:
            self._recents.set_last_open_dir(os.path.dirname(p))
        except Exception:
            pass
        self._open_project_path(p)

    def _on_dm_project_loaded(self, file_path: str) -> None:
        p = str(file_path or "").strip()
        if p:
            try:
                self._recents.set_last_open_dir(os.path.dirname(p))
            except Exception:
                pass
        self._push_recent(file_path)
        try:
            self._dirty_tracker.clear_dirty()
        except Exception:
            pass
        try:
            self._refresh.request("project_loaded", force=True)
        except Exception:
            log.debug("project_loaded refresh request failed (best-effort).", exc_info=True)
        self._update_window_title()

    def _on_dm_project_saved(self, file_path: str) -> None:
        p = str(file_path or "").strip()
        if p:
            folder = os.path.dirname(p)
            try:
                self._recents.set_last_open_dir(folder)
                self._recents.set_last_save_dir(folder)
            except Exception:
                pass
        self._push_recent(file_path)
        try:
            self._dirty_tracker.clear_dirty()
        except Exception:
            pass
        self._update_window_title()

    def _on_dm_dirty_changed(self, _is_dirty: bool) -> None:
        try:
            self._dirty_tracker.sync_from_model(bool(_is_dirty))
        except Exception:
            pass
        self._update_window_title()

    def _register_screen_undo_stacks(self) -> None:
        try:
            for i in range(self.app_widget.count()):
                w = self.app_widget.widget(i)
                stack = getattr(w, "undo_stack", None)
                if stack is None:
                    continue
                try:
                    self._undo_group.addStack(stack)
                except Exception:
                    pass
        except Exception:
            log.debug("Failed to register undo stacks (best-effort).", exc_info=True)

    def _set_active_undo_stack(self, index: int | None = None) -> None:
        try:
            _ = index
            idx = int(self.app_widget.currentIndex())
            if idx < 0 or idx >= self.app_widget.count():
                return
            w = self.app_widget.widget(idx)
            stack = getattr(w, "undo_stack", None)
            if stack is not None:
                self._undo_group.setActiveStack(stack)
        except Exception:
            pass

    def _apply_undo_limit_to_screens(self, limit: int) -> None:
        for i in range(self.app_widget.count()):
            try:
                w = self.app_widget.widget(i)
                if hasattr(w, "apply_undo_limit"):
                    w.apply_undo_limit(int(limit))
                else:
                    stack = getattr(w, "undo_stack", None)
                    if stack is not None:
                        stack.setUndoLimit(int(limit))
            except Exception:
                pass

    def _open_undo_settings_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Configuración Undo/Redo")
        layout = QVBoxLayout(dlg)
        row = QHBoxLayout()
        row.addWidget(QLabel("Límite de historial (pasos):", dlg))
        spin = QSpinBox(dlg)
        spin.setRange(1, 100)
        spin.setValue(get_int("ui/undo_limit", 10))
        row.addWidget(spin)
        layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec_() == QDialog.Accepted:
            try:
                val = int(spin.value())
                set_int("ui/undo_limit", val)
                self._apply_undo_limit_to_screens(val)
            except Exception:
                pass

    def _persist_last_main_tab(self, idx: int) -> None:
        try:
            _ = idx
            set_int(self.KEY_LAST_MAIN_TAB, int(self.app_widget.currentIndex()))
        except Exception:
            pass

    def _restore_last_main_tab(self) -> None:
        try:
            idx = get_int(self.KEY_LAST_MAIN_TAB, int(self.app_widget.currentIndex()))
        except Exception:
            idx = 0
        try:
            if 0 <= int(idx) < self.app_widget.count():
                self.app_widget.setCurrentIndex(int(idx))
            self.sidebar.set_active(self.app_widget.currentIndex())
        except Exception:
            pass

    def _update_window_title(self) -> None:
        try:
            dm = self.data_model
            dirty = bool(getattr(self._dirty_tracker, "is_dirty", getattr(dm, "dirty", False)))
            file_path = str(getattr(dm, "file_path", "") or "")
            name = ""
            try:
                if file_path:
                    name = os.path.basename(file_path)
                else:
                    name = str(getattr(dm, "project_filename", "") or "").strip()
            except Exception:
                name = ""
            suffix = f" — {name}" if name else ""
            star = " *" if dirty else ""
            self.setWindowTitle(self._base_title + suffix + star)
        except Exception:
            self.setWindowTitle(self._base_title)

    def _sync_sidebar_initial_state(self) -> None:
        """Asegura estilo/seleccion correctos de sidebar al arranque."""
        try:
            if hasattr(self, "app_widget") and hasattr(self, "sidebar"):
                idx = int(self.app_widget.currentIndex())
                if hasattr(self.sidebar, "set_active"):
                    self.sidebar.set_active(idx)

            self._apply_ui_tags_and_repolish(self._central)
        except Exception:
            pass

    def _on_refresh_finished_apply_ui(self) -> None:
        try:
            self.sidebar.set_active(self.app_widget.currentIndex())
        except Exception:
            pass
        self._apply_ui_tags_and_repolish(self._central)

    def _after_refresh_restore_screen_states(self) -> None:
        def _run() -> None:
            try:
                active = self.app_widget.currentWidget()
                restore_screen_state(active)

                screens = iter_main_screens(self.app_widget)
                delay_idx = 0
                for s in screens:
                    if s is active:
                        continue
                    delay_idx += 1
                    QTimer.singleShot(10 * delay_idx, lambda s=s: restore_screen_state(s))
            except Exception:
                log.debug("Global post-refresh screen restore failed (best-effort).", exc_info=True)
            finally:
                try:
                    self.sidebar.set_active(self.app_widget.currentIndex())
                except Exception:
                    pass

        try:
            QTimer.singleShot(0, _run)
        except Exception:
            _run()

    def _persist_all_screen_states(self) -> None:
        try:
            for s in iter_main_screens(self.app_widget):
                persist_screen_state(s)
        except Exception:
            log.debug("Global screen-state persistence failed (best-effort).", exc_info=True)

    def _on_sidebar_navigate(self, tab_index: int) -> None:
        try:
            self.app_widget.setCurrentIndex(int(tab_index))
        except Exception:
            pass

    def _on_tab_changed_for_sidebar(self, index: int) -> None:
        _ = index
        try:
            real_index = int(self.app_widget.currentIndex())
        except Exception:
            real_index = -1
        prev = getattr(self, "_last_tab_widget", None)
        current = None
        try:
            if 0 <= real_index < self.app_widget.count():
                current = self.app_widget.widget(real_index)
        except Exception:
            current = None
        try:
            if prev is not None and prev is not current:
                persist_screen_state(prev)
        except Exception:
            pass
        try:
            if real_index >= 0:
                self.sidebar.set_active(real_index)
        except Exception:
            pass
        try:
            current = self.app_widget.currentWidget()
            if current is not None:
                self._apply_ui_tags_and_repolish(current)
            repolish_tree(self.sidebar)
        except Exception:
            log.debug("Failed to refresh UI style on tab change (best-effort).", exc_info=True)
        try:
            self._last_tab_index = real_index if real_index >= 0 else self.app_widget.currentIndex()
        except Exception:
            self._last_tab_index = self.app_widget.currentIndex()
        try:
            self._last_tab_widget = self.app_widget.currentWidget()
        except Exception:
            self._last_tab_widget = None
        try:
            self._set_active_undo_stack(real_index)
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
        for widget in (self, getattr(self, "_central", None), self.app_widget, self.sidebar):
            if widget is None:
                continue
            widget.setProperty("glass", is_modern)
            widget.setProperty("ui_mode", mode)
        for t in self.app_widget.findChildren(QTabWidget):
            t.setProperty("glass", is_modern)
        for table in self.app_widget.findChildren(QTableWidget):
            table.setProperty("glass", is_modern)
        self._apply_ui_tags_and_repolish(self._central)

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

        self._recent_menu = file_menu.addMenu("Abrir reciente")
        self._recent_menu.aboutToShow.connect(self._rebuild_recent_menu)
        self._rebuild_recent_menu()

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

        # Edición
        edit_menu = menubar.addMenu("Edición")
        undo_action = self._undo_group.createUndoAction(self, "Deshacer")
        undo_action.setShortcut("Ctrl+Z")
        edit_menu.addAction(undo_action)
        redo_action = self._undo_group.createRedoAction(self, "Rehacer")
        redo_action.setShortcut("Ctrl+Y")
        edit_menu.addAction(redo_action)

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
        tools_menu.addSeparator()
        undo_cfg_action = QAction("Configuración Undo/Redo…", self)
        undo_cfg_action.triggered.connect(self._open_undo_settings_dialog)
        tools_menu.addAction(undo_cfg_action)

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
            self._apply_ui_tags_and_repolish(self._central)
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
    def _confirm_unsaved_changes(self, *, context: str) -> bool:
        """Unified Guardar/No guardar/Cancelar flow.

        Returns True if caller can continue, False if user canceled.
        """
        tracker = getattr(self, "_dirty_tracker", None)
        if tracker is not None and not bool(getattr(tracker, "is_dirty", False)):
            return True
        if tracker is None and not bool(getattr(self.data_model, "dirty", False)):
            return True

        action_text = str(context or "continuar")
        reply = QMessageBox.question(
            self,
            "Cambios sin guardar",
            f"Hay cambios sin guardar. ¿Deseas guardarlos antes de {action_text}?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Save:
            self.save_project_from_menu()
            dirty_now = bool(getattr(self.data_model, "dirty", False))
            try:
                if tracker is not None:
                    tracker.sync_from_model(dirty_now, force=True)
            except Exception:
                pass
            return not dirty_now
        return True

    def _maybe_prompt_save_if_dirty(self) -> bool:
        """Retorna True si se puede continuar (sin cancelar)."""
        return self._confirm_unsaved_changes(context="continuar")

    def _open_project_path(self, file_path: str) -> None:
        if not file_path:
            return
        if self._proj_open_in_progress:
            return
        self._proj_open_in_progress = True

        try:
            tab_before = int(self.app_widget.currentIndex())
        except Exception:
            tab_before = 0

        prog = QProgressDialog("Cargando proyecto…", "", 0, 0, self)
        prog.setWindowTitle("SS/AA")
        prog.setWindowModality(Qt.WindowModal)
        prog.setCancelButton(None)
        prog.setMinimumDuration(0)
        prog.show()
        QApplication.processEvents()
        self._begin_ui_freeze()
        tracking_suspended = False
        try:
            self._dirty_tracker.suspend()
            tracking_suspended = True
        except Exception:
            tracking_suspended = False

        finalized = {"done": False}

        def _finalize_open_once() -> None:
            if finalized.get("done"):
                return
            finalized["done"] = True
            try:
                refresh_obj = getattr(self, "_refresh", None)
                if refresh_obj is not None:
                    refresh_obj.refresh_finished.disconnect(_on_refresh_finished_any)
            except Exception:
                pass
            try:
                self.app_widget.refresh_finished.disconnect(_on_app_refresh_finished)
            except Exception:
                pass
            try:
                blocker = QSignalBlocker(self.app_widget)
                try:
                    if 0 <= tab_before < self.app_widget.count():
                        self.app_widget.setCurrentIndex(tab_before)
                finally:
                    del blocker
            except Exception:
                pass
            try:
                self.sidebar.set_active(self.app_widget.currentIndex())
            except Exception:
                pass
            try:
                from ui.utils.style_utils import repolish_tree as _repolish_tree
                _repolish_tree(self._central)
            except Exception:
                pass
            self._end_ui_freeze()
            try:
                self.app_widget.setUpdatesEnabled(True)
                self.app_widget.update()
                self.app_widget.repaint()
                tb_fn = getattr(self.app_widget, "tabBar", None)
                if callable(tb_fn):
                    tb = tb_fn()
                    if tb is not None:
                        tb.update()
                        tb.repaint()
            except Exception:
                pass
            try:
                prog.close()
            except Exception:
                pass
            try:
                if tracking_suspended:
                    self._dirty_tracker.resume()
                self._dirty_tracker.sync_from_model(bool(getattr(self.data_model, "dirty", False)), force=True)
            except Exception:
                pass

        def _on_refresh_finished_any(*_args) -> None:
            _finalize_open_once()

        def _on_app_refresh_finished() -> None:
            _finalize_open_once()

        try:
            try:
                refresh_obj = getattr(self, "_refresh", None)
                if refresh_obj is not None:
                    refresh_obj.refresh_finished.connect(_on_refresh_finished_any)
            except Exception:
                pass
            try:
                self.app_widget.refresh_finished.connect(_on_app_refresh_finished)
            except Exception:
                pass

            self.data_model.load_from_file(file_path)

            prog.setLabelText("Actualizando pantallas…")
            QApplication.processEvents()
            try:
                self._refresh.request("project_loaded", force=True)
            except Exception:
                QTimer.singleShot(0, self.app_widget.actualizar_pantallas)
        except Exception as e:
            try:
                refresh_obj = getattr(self, "_refresh", None)
                if refresh_obj is not None:
                    refresh_obj.refresh_finished.disconnect(_on_refresh_finished_any)
            except Exception:
                pass
            try:
                self.app_widget.refresh_finished.disconnect(_on_app_refresh_finished)
            except Exception:
                pass
            _finalize_open_once()
            QMessageBox.critical(self, "Error", f"No se pudo abrir el proyecto:\n\n{e}")
            return

        QTimer.singleShot(
            15000,
            lambda: _finalize_open_once() if self._proj_open_in_progress else None,
        )

    def open_project_from_menu(self):
        if not self._maybe_prompt_save_if_dirty():
            return

        start_dir = str(self._recents.get_last_open_dir("")).strip() or (self.data_model.project_folder or "")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir proyecto",
            start_dir,
            "Proyecto SS/AA (*.ssaa *.json);;Todos los archivos (*.*)",
        )
        if not file_path:
            return
        self._recents.set_last_open_dir(os.path.dirname(file_path))
        self._open_project_path(file_path)

    def save_project_from_menu(self):
        """Guardar (Ctrl+S). Si no hay archivo asociado, actúa como Guardar como…"""
        dm = self.data_model
        self.app_widget.commit_pending_edits()

        if not getattr(dm, "file_path", None):
            self.save_as_project_from_menu()
            return

        prog = QProgressDialog("Guardando proyecto…", "", 0, 0, self)
        prog.setWindowTitle("SS/AA")
        prog.setWindowModality(Qt.WindowModal)
        prog.setCancelButton(None)
        prog.setMinimumDuration(0)
        prog.show()
        QApplication.processEvents()
        try:
            dm.save_to_file()  # usa dm.file_path actual
            try:
                self._recents.set_last_save_dir(os.path.dirname(dm.file_path))
            except Exception:
                pass
            QMessageBox.information(self, "Guardar proyecto", "Proyecto guardado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el proyecto:\n\n{e}")
        finally:
            try:
                prog.close()
            except Exception:
                pass

    def save_as_project_from_menu(self):
        dm = self.data_model
        self.app_widget.commit_pending_edits()

        base_name = getattr(dm, "project_filename", "") or "proyecto_ssaa"
        default_name = base_name if str(base_name).lower().endswith(".ssaa") else f"{base_name}.ssaa"
        start_dir = str(self._recents.get_last_save_dir("")).strip() or (getattr(dm, "project_folder", "") or "")
        start_path = os.path.join(start_dir, default_name) if start_dir else default_name
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar proyecto como",
            start_path,
            "Proyecto SS/AA (*.ssaa)",
        )
        if not file_path:
            return

        if not file_path.lower().endswith(".ssaa"):
            file_path += ".ssaa"

        prog = QProgressDialog("Guardando proyecto…", "", 0, 0, self)
        prog.setWindowTitle("SS/AA")
        prog.setWindowModality(Qt.WindowModal)
        prog.setCancelButton(None)
        prog.setMinimumDuration(0)
        prog.show()
        QApplication.processEvents()
        try:
            dm.save_to_file(file_path)
            self._recents.set_last_save_dir(os.path.dirname(file_path))
            QMessageBox.information(self, "Guardar proyecto", "Proyecto guardado correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el proyecto:\n\n{e}")
        finally:
            try:
                prog.close()
            except Exception:
                pass

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
        try:
            for screen in iter_main_screens(self.app_widget):
                try:
                    checker = getattr(screen, "can_close", None)
                    if callable(checker) and not bool(checker(self)):
                        event.ignore()
                        return
                except Exception:
                    continue
        except Exception:
            pass

        if not self._confirm_unsaved_changes(context="salir"):
            event.ignore()
            return
        event.accept()


def create_main_window() -> MainWindow:
    """Factory used by main.py."""
    return MainWindow()
