# -*- coding: utf-8 -*-
"""
Pantalla de Consumos (gabinetes).

Incluye:
- Tabla con TAG, Marca, Modelo, Potencia [W], Potencia [VA], Usar VA,
  Tipo de Consumo, Fase (1F/3F) y Origen.
- Tarjetas gráficas que muestran TAG, tipo de consumo, fase (solo para C.A.)
  y potencia con unidades [W] o [VA].

Compatibilidad:
- Si en los datos del componente existe "potencia" o "potencia_cc"
  (versiones antiguas), se mapean a "potencia_w".
- Si no existe "fase", se asume "1F".
"""
import os
import json
import uuid
import copy
from pathlib import Path
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from screens.base import ScreenBase
from app.sections import Section

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QStyleOptionGraphicsItem, QGraphicsRectItem,
    QTableWidget, QTableWidgetItem, QComboBox, QCheckBox, QMenu, QMessageBox,
    QHeaderView, QGroupBox
)

from ui.common.state import save_header_state, restore_header_state
from ui.theme import get_theme_token

from PyQt5.QtCore import Qt, QPointF, QRectF, QMimeData, pyqtSignal, QTimer, QSignalBlocker
from PyQt5.QtGui import QBrush, QColor, QPainter, QPen, QDrag, QFont
from ui.table_utils import make_table_sortable
from ui.table_utils import center_in_cell
from ui.utils.table_utils import configure_table_autoresize

from .graphics import (
    GRID_SIZE, CABINET_MARGIN, CABINET_WIDTH, CABINET_HEIGHT, EXTRA_SCROLL, DEFAULT_SIZE,
    COLOR_FRAME, COLOR_GRID_LIGHT, FONT_ITEM,
    ComponentCardItem, CustomGraphicsView,
)
try:
    from SSAA.widgets.grouped_equipment_tree_widget import GroupedEquipmentTreeWidget
except Exception:  # pragma: no cover - local execution fallback
    from widgets.grouped_equipment_tree_widget import GroupedEquipmentTreeWidget
from .persistence import CabinetPersistence
from .update_pipeline import CabinetUpdatePipeline
from .cabinet_controller import CabinetController
from .normalize import normalize_comp_data
from .constants import (
    COL_EQUIPO, COL_TAG, COL_MARCA, COL_MODELO, COL_P_W, COL_P_VA,
    COL_USAR_VA, COL_ALIMENTADOR, COL_TIPO, COL_FASE, COL_ORIGEN,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # screen.py -> cabinet -> screens -> PROJECT_ROOT

# Backward-compat: antiguamente existía resources/component_database.json.
# Desde Stage 7.8, el catálogo recomendado es una librería .lib
# cargada por el usuario (Gestor de librerías). Aquí mantenemos
# fallback al JSON antiguo si existe.
COMPONENT_DB_FILE = str(PROJECT_ROOT / "resources" / "component_database.json")

# índices de columnas de la tabla (ver screens/cabinet/constants.py)

# ============================================================
#  Lista de equipos arrastrables
# ============================================================
# ============================================================
#  Vista personalizada con rejilla y drop
# ============================================================
# ============================================================
#  Pantalla principal de Componentes
# ============================================================
class CabinetComponentsScreen(ScreenBase):
    SECTION = Section.CABINET
    # se emitirá cada vez que cambie algo en los componentes
    data_changed = pyqtSignal()

    def __init__(self, data_model, parent=None):
        super().__init__(data_model, parent)
        self.data_model = data_model
        self._persistence = CabinetPersistence(self.data_model, COMPONENT_DB_FILE)
        self._controller = CabinetController(self)
        self._pipeline = CabinetUpdatePipeline(self)
        self.current_cabinet = None
        self.row_by_id = {}
        self.cards_by_id = {}
        self._loading = False
        self._in_user_edit = False
        self._pending_refresh = False
        self._ui_updating_depth = 0
        self._copied_cabinet_components = None
        self._copied_cabinet_info = None

        self.scene = QGraphicsScene(self)
        self._dynamic_height = self._cabinet_min_height()
        self.view = CustomGraphicsView(self.scene, self, self)

        self._frame_item = None
        self._cabinet_title_item = None
        self._cab_title_bg = None

        self._init_ui()
        self.load_equipment()
        self.load_cabinets()

    def _combo_text_at(self, row: int, col: int) -> str:
        """
        Devuelve el texto actual de un QComboBox en la tabla, o el texto
        del QTableWidgetItem si no hay combo en esa celda.
        """
        widget = self.table.cellWidget(row, col)
        if isinstance(widget, QComboBox):
            return widget.currentText()

        item = self.table.item(row, col)
        return item.text() if item is not None else ""

    @contextmanager
    def _ui_update(self):
        self._ui_updating_depth += 1
        try:
            with QSignalBlocker(self.table):
                yield
        finally:
            self._ui_updating_depth -= 1

    def _ui_updating(self) -> bool:
        return self._ui_updating_depth > 0

    def _ensure_item(self, row: int, col: int, text: str = "") -> QTableWidgetItem:
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem(text)
            self.table.setItem(row, col, item)
        return item

    def _set_cell_editable(self, row: int, col: int, editable: bool) -> None:
        item = self._ensure_item(row, col, "")
        flags = item.flags()
        if editable:
            item.setFlags(flags | Qt.ItemIsEditable)
            item.setBackground(QBrush(QColor(get_theme_token("INPUT_EDIT_BG", "#FFF9C4"))))
        else:
            item.setFlags(flags & ~Qt.ItemIsEditable)
            item.setBackground(QBrush(QColor(get_theme_token("SURFACE", "#FFFFFF"))))

    def _begin_user_edit(self):
        self._in_user_edit = True

    def _end_user_edit(self):
        self._in_user_edit = False
        if self._pending_refresh:
            self._pending_refresh = False
            QTimer.singleShot(0, self._safe_refresh)

    def _safe_refresh(self):
        if self._in_user_edit:
            self._pending_refresh = True
            return
        try:
            with QSignalBlocker(self.table):
                self.update_design_view()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)


    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------
    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # panel izquierdo: gabinetes
        left_group = QGroupBox("Gabinetes")
        left = QVBoxLayout()
        left.setSpacing(8)
        self.cabinets_list = QListWidget()
        self.cabinets_list.currentRowChanged.connect(self._on_select_cabinet)
        # menú contextual para copiar/pegar consumos entre gabinetes
        self.cabinets_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.cabinets_list.customContextMenuRequested.connect(
            self._show_cabinet_context_menu
        )
        left.addWidget(self.cabinets_list)
        left_group.setLayout(left)
        root.addWidget(left_group, 1)

        # panel central: vista + tabla
        center = QVBoxLayout()
        center.setSpacing(10)

        design_group = QGroupBox("Diseño del gabinete")
        design_layout = QVBoxLayout()
        design_layout.setSpacing(8)
        design_layout.addWidget(self.view)
        design_group.setLayout(design_layout)
        center.addWidget(design_group, 3)

        table_group = QGroupBox("Consumos del gabinete")
        table_layout = QVBoxLayout()
        table_layout.setSpacing(8)
        self.table = QTableWidget(0, 11, self)
        self.table.setHorizontalHeaderLabels([
            "Equipo",
            "TAG",
            "Marca",
            "Modelo",
            "P [W]",
            "P [VA]",
            "Usar VA",
            "Alimentador",
            "Tipo Consumo",
            "Fase",
            "Origen",
        ])
        configure_table_autoresize(self.table)
        restore_header_state(self.table.horizontalHeader(), "cabinet.components.table.header")

        # ---> activar ordenamiento
        make_table_sortable(self.table)

        self.table.itemChanged.connect(self._on_table_item_changed)
        table_layout.addWidget(self.table)
        table_group.setLayout(table_layout)
        center.addWidget(table_group, 2)
        root.addLayout(center, 3)

        # panel derecho: componentes disponibles
        right_group = QGroupBox("Consumos")
        right = QVBoxLayout()
        right.setSpacing(8)
        self.equipment_tree = GroupedEquipmentTreeWidget(self)
        self.equipment_tree.equipmentActivated.connect(self._add_equipment_to_cabinet)
        right.addWidget(self.equipment_tree)
        right_group.setLayout(right)
        root.addWidget(right_group, 1)

    # --------------------------------------------------------
    # Carga de datos
    # --------------------------------------------------------
    def _load_component_database(self):
        """Wrapper: delega a CabinetPersistence.load_component_database()."""
        return self._persistence.load_component_database()

    def load_cabinets(self):
        """
        Recarga la lista de gabinetes desde el data_model.

        - Se llama al inicio.
        - Se llama también cuando LocationScreen emite cabinets_updated.
        - Intenta mantener el gabinete actualmente seleccionado (por TAG).
        """
        gabinetes = getattr(self.data_model, "gabinetes", [])

        # Recordar el TAG del gabinete actualmente seleccionado (si hay)
        prev_tag = None
        if self.current_cabinet is not None:
            prev_tag = self.current_cabinet.get("tag", "")

        # Refrescar la lista visual
        self.cabinets_list.blockSignals(True)
        self.cabinets_list.clear()
        for g in gabinetes:
            tag = g.get("tag", "")
            nombre = g.get("nombre", "")
            it = QListWidgetItem(f"{tag} - {nombre}")
            it.setData(Qt.UserRole, tag)
            self.cabinets_list.addItem(it)
        self.cabinets_list.sortItems(Qt.AscendingOrder)
        self.cabinets_list.blockSignals(False)

        # Mantener selección por TAG en la lista ya ordenada
        selected_row = -1
        if prev_tag:
            for i in range(self.cabinets_list.count()):
                it = self.cabinets_list.item(i)
                if (it.data(Qt.UserRole) or "") == prev_tag:
                    selected_row = i
                    break

        if selected_row < 0 and self.cabinets_list.count() > 0:
            selected_row = 0

        if selected_row >= 0:
            self.cabinets_list.setCurrentRow(selected_row)
            item = self.cabinets_list.item(selected_row)
            selected_tag = (item.data(Qt.UserRole) or "") if item is not None else ""
            self.current_cabinet = next(
                (g for g in gabinetes if str(g.get("tag", "")) == str(selected_tag)),
                None,
            )
        else:
            self.current_cabinet = None

        # Redibujar vista y tabla según el gabinete seleccionado
        self.update_design_view()

  # --------------------------------------------------------
    # Selección de gabinete desde la lista
    # --------------------------------------------------------
    def _on_select_cabinet(self, row: int):
        """
        Se ejecuta cuando el usuario cambia la selección de la lista de gabinetes.
        Actualiza el gabinete actual y redibuja la escena y la tabla.
        """
        gabinetes = getattr(self.data_model, "gabinetes", [])
        item = self.cabinets_list.item(row) if row >= 0 else None
        tag = item.data(Qt.UserRole) if item is not None else None
        if tag:
            self.current_cabinet = next(
                (g for g in gabinetes if str(g.get("tag", "")) == str(tag)),
                None,
            )
        else:
            self.current_cabinet = None

        self._dynamic_height = self._cabinet_min_height()
        self.update_design_view()

    # --------------------------------------------------------
    # Copiar / pegar consumos entre gabinetes
    # --------------------------------------------------------
    def _show_cabinet_context_menu(self, pos):
        item = self.cabinets_list.itemAt(pos)
        row = self.cabinets_list.row(item) if item is not None else -1

        menu = QMenu(self)
        act_copy = menu.addAction("Copiar consumos de este gabinete")
        act_paste = menu.addAction("Pegar consumos en este gabinete")

        if row < 0:
            act_copy.setEnabled(False)
            act_paste.setEnabled(False)

        if not self._copied_cabinet_components:
            act_paste.setEnabled(False)

        action = menu.exec_(self.cabinets_list.mapToGlobal(pos))

        gabinetes = getattr(self.data_model, "gabinetes", [])

        if action == act_copy and 0 <= row < len(gabinetes):
            source_cab = gabinetes[row]
            self._copied_cabinet_components = self._copy_cabinet_components(source_cab)
            self._copied_cabinet_info = {
                "tag": source_cab.get("tag", ""),
                "nombre": source_cab.get("nombre", ""),
            }

        elif action == act_paste:
            self._paste_cabinet_components(row)

    def _copy_cabinet_components(self, source_cab, only_selected=False):
        return self._controller.copy_cabinet_components(source_cab, only_selected=only_selected)

    def _paste_cabinet_components(self, row: int = None):
        return self._controller.paste_cabinet_components(row=row)

    def _normalize_comp_data(self, data: dict) -> dict:
        """Wrapper: delega a normalize_comp_data() (módulo puro, sin Qt)."""
        return normalize_comp_data(data)

    def _draw_cabinet_frame(self):
        if self._frame_item:
            self.scene.removeItem(self._frame_item)
            self._frame_item = None

        rect = QRectF(
            CABINET_MARGIN,
            CABINET_MARGIN,
            CABINET_WIDTH,
            self._dynamic_height,
        )
        pen = QPen(COLOR_FRAME, 2.2)
        pen.setCosmetic(True)

        item = self.scene.addRect(rect, pen)
        item.setZValue(-1)
        self._frame_item = item

    def _show_cabinet_title(self):
        if self._cabinet_title_item:
            self.scene.removeItem(self._cabinet_title_item)
            self._cabinet_title_item = None
        if self._cab_title_bg:
            self.scene.removeItem(self._cab_title_bg)
            self._cab_title_bg = None
        if not self.current_cabinet:
            return

        title = f"{self.current_cabinet.get('tag', '')} - {self.current_cabinet.get('nombre', '')}"
        t = self.scene.addText(title, QFont("Segoe UI", 11, QFont.DemiBold))
        t.setDefaultTextColor(QColor(48, 48, 48))
        t.setZValue(3)
        r = t.boundingRect()

        pad_x, pad_y = 8, 4
        bg_rect = QRectF(0, 0, r.width() + 2 * pad_x, r.height() + 2 * pad_y)
        bg_x = CABINET_MARGIN + (CABINET_WIDTH - bg_rect.width()) / 2
        bg_y = max(0, CABINET_MARGIN - bg_rect.height() - 4)

        bg = QGraphicsRectItem(bg_rect)
        bg.setBrush(QBrush(Qt.white))
        bg.setPen(QPen(QColor(190, 190, 190), 1))
        bg.setZValue(2)
        bg.setPos(bg_x, bg_y)
        self.scene.addItem(bg)

        t.setPos(QPointF(bg_x + pad_x, bg_y + pad_y))
        self._cab_title_bg = bg
        self._cabinet_title_item = t

    def _cabinet_min_height(self) -> int:
        return int(max(DEFAULT_SIZE[1] + 2 * GRID_SIZE + 2 * CABINET_MARGIN, 220))

    def _ensure_scene_fits(self):
        max_bottom = CABINET_MARGIN
        for item in self.scene.items():
            if isinstance(item, ComponentCardItem):
                br = item.mapRectToScene(item.boundingRect())
                max_bottom = max(max_bottom, br.bottom() + CABINET_MARGIN)

        min_height = self._cabinet_min_height()
        self._dynamic_height = max(min_height, max_bottom - CABINET_MARGIN)
        total_height = self._dynamic_height + EXTRA_SCROLL
        self.scene.setSceneRect(0, 0, CABINET_MARGIN * 2 + CABINET_WIDTH, total_height)

    def _pos_to_xy(self, pos):
        # acepta dict {"x":..,"y":..} o lista/tupla (x,y)
        if isinstance(pos, dict):
            x = pos.get("x", 0)
            y = pos.get("y", 0)
            return float(x or 0), float(y or 0)
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            return float(pos[0] or 0), float(pos[1] or 0)
        return 0.0, 0.0

    def _size_to_wh(self, size):
        # acepta dict {"w":..,"h":..} o lista/tupla (w,h)
        if isinstance(size, dict):
            w = size.get("w", DEFAULT_SIZE[0])
            h = size.get("h", DEFAULT_SIZE[1])
            return float(w or DEFAULT_SIZE[0]), float(h or DEFAULT_SIZE[1])
        if isinstance(size, (list, tuple)) and len(size) >= 2:
            return float(size[0] or DEFAULT_SIZE[0]), float(size[1] or DEFAULT_SIZE[1])
        return float(DEFAULT_SIZE[0]), float(DEFAULT_SIZE[1])

    def update_design_view(self):
        if getattr(self, "_in_user_edit", False):
            self._pending_refresh = True
            return
        self._loading = True
        self.scene.clear()
        self.row_by_id.clear()
        self.cards_by_id.clear()
        self._frame_item = None
        self._cabinet_title_item = None
        self._cab_title_bg = None

        if not self.current_cabinet:
            self.table.setRowCount(0)
            self._dynamic_height = self._cabinet_min_height()
            total_height = self._dynamic_height + EXTRA_SCROLL
            self.scene.setSceneRect(0, 0, CABINET_MARGIN * 2 + CABINET_WIDTH, total_height)
            self._loading = False
            return

        components = self.current_cabinet.setdefault("components", [])
        self.table.setRowCount(0)

        used_positions = set()

        def _snap(x, y):
            x = round(x / GRID_SIZE) * GRID_SIZE
            y = round(y / GRID_SIZE) * GRID_SIZE
            return int(x), int(y)

        def _auto_place(i):
            # layout simple en columnas
            cols = max(1, int((CABINET_WIDTH - 2*CABINET_MARGIN) // (DEFAULT_SIZE[0] + GRID_SIZE)))
            col = i % cols
            row = i // cols
            x = CABINET_MARGIN + GRID_SIZE + col * (DEFAULT_SIZE[0] + GRID_SIZE)
            y = CABINET_MARGIN + GRID_SIZE + row * (DEFAULT_SIZE[1] + GRID_SIZE)
            return _snap(x, y)

        for comp in components:
            comp_id = comp.setdefault("id", str(uuid.uuid4()))
            name = comp.setdefault("name", comp.get("base", "Equipo"))

            pos_raw = comp.get("pos", (CABINET_MARGIN + GRID_SIZE, CABINET_MARGIN + GRID_SIZE))
            size_raw = comp.get("size", DEFAULT_SIZE)

            x, y = self._pos_to_xy(pos_raw)
            sx, sy = _snap(x, y)

            # si pos es 0,0 o ya está ocupada, auto-ubicar
            if (sx, sy) == (0, 0) or (sx, sy) in used_positions:
                sx, sy = _auto_place(len(used_positions))

            used_positions.add((sx, sy))
            x, y = sx, sy

            # ✅ calcular tamaño desde size_raw
            w, h = self._size_to_wh(size_raw)
            w, h = int(w), int(h)

            # ✅ FALTABA ESTO
            data = self._normalize_comp_data(comp.setdefault("data", {}))

            card = ComponentCardItem(
                comp_id,
                name,
                QPointF(x, y),
                (w, h),
                data,
                self._on_card_moved,
            )
            self.cards_by_id[comp_id] = card
            self.scene.addItem(card)

            self._append_table_row(comp_id, name, data)

        self._ensure_scene_fits()
        self._draw_cabinet_frame()
        self._show_cabinet_title()
        self._loading = False

    def _get_default_component_data(self, base_name: str, lib_uid: str = "") -> dict:
        """
        Obtiene los datos por defecto desde component_database.json
        para un tipo de equipo (mismo 'name').

        - Si hay varias entradas con el mismo nombre, se prefiere la de
          origen 'Genérico'. Si no existe, se usa la primera que aparezca.
        """
        base_name = (base_name or "").strip()
        if not base_name:
            return {}

        # Preferimos consumos cargados desde librería
        lib = getattr(self.data_model, "library_data", {}).get("consumos")
        db_components = []
        if isinstance(lib, dict) and lib.get("file_type") == "SSAA_LIB_CONSUMOS":
            raw_items = lib.get("items", [])
            if isinstance(raw_items, list):
                db_components = [it for it in raw_items if isinstance(it, dict)]
        if not db_components:
            db_components = self._load_component_database()

        if lib_uid:
            same = [c for c in db_components if str(c.get("lib_uid", "")).strip() == lib_uid]
        else:
            same = [
                c for c in db_components
                if str(c.get("name", "")).strip() == base_name
            ]
        if not same:
            return {}

        generic = [c for c in same if c.get("origen", "Genérico") == "Genérico"]
        chosen = generic[0] if generic else same[0]

        # Normalizamos para que tenga todas las claves esperadas
        d = self._normalize_comp_data(dict(chosen))
        # El TAG siempre se define por gabinete, no viene de la base
        d["tag"] = ""
        return d

    # --------------------------------------------------------
    # Operaciones sobre componentes
    # --------------------------------------------------------
    def add_component_at(self, base_name: str, pos: QPointF, lib_uid: str = "", code: str = ""):
        if not self.current_cabinet:
            return

        comps = self.current_cabinet.setdefault("components", [])
        count_same = sum(1 for c in comps if c.get("base") == base_name)
        display_name = f"{base_name} ({count_same + 1})" if count_same else base_name

        comp_id = str(uuid.uuid4())

        # 👉 intentamos leer los datos por defecto desde la base
        data = self._get_default_component_data(base_name, lib_uid=lib_uid)
        if not data:
            # si no hay nada en la base, usamos valores vacíos
            data = {
                "tag": "",
                "marca": "",
                "modelo": "",
                "potencia_w": "",
                "potencia_va": "",
                "usar_va": False,
                "tipo_consumo": "C.C. permanente",
                "fase": "1F",
                "origen": "Genérico",
            }

        comp = {
            "id": comp_id,
            "base": base_name,
            "name": display_name,
            "pos": [float(pos.x()), float(pos.y())],
            "size": [float(DEFAULT_SIZE[0]), float(DEFAULT_SIZE[1])],
            "data": data,
        }
        # Vínculo con librería (solo si fue insertado desde consumos.lib)
        if lib_uid:
            comp["source"] = {
                "type": "consumos_lib",
                "lib_uid": str(lib_uid),
                "code": str(code or ""),
                "lib_path": str(getattr(self.data_model, "library_paths", {}).get("consumos", "") or ""),
            }
        comps.append(comp)
        self._pipeline.after_mutation(rebuild_view=True, emit=True, dirty=True)

    def remove_component_item(self, item: ComponentCardItem):
        if not self.current_cabinet:
            return
        comp_id = item.comp_id
        comps = self.current_cabinet.get("components", [])
        self.current_cabinet["components"] = [c for c in comps if c.get("id") != comp_id]
        self._pipeline.after_mutation(rebuild_view=True, emit=True, dirty=True)

    def _on_card_moved(self, comp_id: str, pos: QPointF):
        if not self.current_cabinet:
            return
        for comp in self.current_cabinet.get("components", []):
            if comp.get("id") == comp_id:
                comp["pos"] = [float(pos.x()), float(pos.y())]
                break
        self._pipeline.after_card_move(dirty=True)

    # --------------------------------------------------------
    # Tabla de componentes
    # --------------------------------------------------------
    def _append_table_row(self, comp_id: str, name: str, data: dict):
        row = self.table.rowCount()
        self.table.insertRow(row)

        d = self._normalize_comp_data(data)

        it_equipo = QTableWidgetItem(name)
        it_equipo.setData(Qt.UserRole, comp_id)
        it_equipo.setFlags(it_equipo.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, COL_EQUIPO, it_equipo)

        self.table.setItem(row, COL_TAG, QTableWidgetItem(str(d.get("tag", ""))))
        self.table.setItem(row, COL_MARCA, QTableWidgetItem(str(d.get("marca", ""))))
        self.table.setItem(row, COL_MODELO, QTableWidgetItem(str(d.get("modelo", ""))))
        self.table.setItem(row, COL_P_W, QTableWidgetItem(str(d.get("potencia_w", ""))))
        self.table.setItem(row, COL_P_VA, QTableWidgetItem(str(d.get("potencia_va", ""))))

        # Usar VA (UN SOLO checkbox, centrado)
        chk_va = QCheckBox()
        chk_va.setChecked(bool(d.get("usar_va", False)))
        chk_va.stateChanged.connect(
            lambda state, cid=comp_id: self._sync_from_table(cid, "usar_va", state == Qt.Checked)
        )
        self.table.setCellWidget(row, COL_USAR_VA, center_in_cell(chk_va))

        # Alimentador
        alimentador_combo = QComboBox()
        alimentador_combo.addItems(["General", "Individual", "Indirecta"])
        with QSignalBlocker(alimentador_combo):
            alimentador_combo.setCurrentText(d.get("alimentador", "General"))
        alimentador_combo.currentTextChanged.connect(
            lambda val, cid=comp_id: self._sync_from_table(cid, "alimentador", val)
        )
        self.table.setCellWidget(row, COL_ALIMENTADOR, alimentador_combo)

        # Tipo consumo
        tipo_combo = QComboBox()
        tipo_combo.addItems([
            "C.C. permanente",
            "C.C. momentáneo",
            "C.C. aleatorio",
            "C.A. Esencial",
            "C.A. No Esencial",
        ])
        with QSignalBlocker(tipo_combo):
            tipo_combo.setCurrentText(d.get("tipo_consumo", "C.C. permanente"))
        tipo_combo.currentTextChanged.connect(
            lambda val, cid=comp_id: self._sync_from_table(cid, "tipo_consumo", val)
        )
        self.table.setCellWidget(row, COL_TIPO, tipo_combo)

        # Fase
        fase_combo = QComboBox()
        fase_combo.addItems(["1F", "3F"])
        with QSignalBlocker(fase_combo):
            fase_combo.setCurrentText(d.get("fase", "1F"))
        fase_combo.currentTextChanged.connect(
            lambda val, cid=comp_id: self._sync_from_table(cid, "fase", val)
        )
        self.table.setCellWidget(row, COL_FASE, fase_combo)

        # Origen
        origen_combo = QComboBox()
        origen_combo.addItems(["Genérico", "Según Fabricante", "Por Usuario"])
        with QSignalBlocker(origen_combo):
            origen_combo.setCurrentText(d.get("origen", "Genérico"))
        origen_combo.setProperty("row", row)
        origen_combo.setProperty("comp_id", comp_id)
        origen_combo.setProperty("key", "origen")
        origen_combo.currentIndexChanged.connect(self._on_origin_changed)
        self.table.setCellWidget(row, COL_ORIGEN, origen_combo)

        self.row_by_id[comp_id] = row

        self._apply_origin_to_row(row, origen_combo.currentText())
        usar_va = bool(chk_va.isChecked())
        self._apply_power_mode_to_row(row, usar_va, tipo_combo.currentText())

    def _get_comp_id_by_row(self, row: int) -> str:
        """Busca el id de componente a partir de la fila de la tabla."""
        for cid, r in self.row_by_id.items():
            if r == row:
                return cid
        return ""

    def _get_db_variants_for(self, base_name: str) -> list:
        """
        Devuelve las variantes de la base de datos para un tipo de equipo dado
        (mismo 'name' y con marca/modelo definidos).
        """
        base_name = (base_name or "").strip()
        if not base_name:
            return []

        variants = []
        for raw in self._load_component_database():
            name = str(raw.get("name", "")).strip()
            if name != base_name:
                continue
            marca = str(raw.get("marca", "")).strip()
            modelo = str(raw.get("modelo", "")).strip()
            if not marca or not modelo:
                # sólo nos interesan los que vienen ya como "según fabricante"
                continue
            variants.append(self._normalize_comp_data(dict(raw)))
        return variants

    def _update_row_from_data(self, row: int, d: dict):
        """
        Refresca las celdas de una fila (potencias, usar VA, tipo consumo, fase)
        a partir de un dict de datos de componente.
        """
        prev = self._loading
        self._loading = True
        try:
            # Potencias
            item_w = self.table.item(row, COL_P_W)
            if item_w is None:
                item_w = QTableWidgetItem("")
                self.table.setItem(row, COL_P_W, item_w)
            pw = d.get("potencia_w", "")
            item_w.setText("" if pw in (None, "") else str(pw))

            item_va = self.table.item(row, COL_P_VA)
            if item_va is None:
                item_va = QTableWidgetItem("")
                self.table.setItem(row, COL_P_VA, item_va)
            pva = d.get("potencia_va", "")
            item_va.setText("" if pva in (None, "") else str(pva))

            # Usar VA
            chk = self._get_checkbox_at(row, COL_USAR_VA)
            if chk is not None:
                self._set_checkbox_checked_safely(chk, bool(d.get("usar_va")))

            # Tipo consumo
            tipo = str(d.get("tipo_consumo", "C.C. permanente"))
            tipo_combo = self.table.cellWidget(row, COL_TIPO)
            if isinstance(tipo_combo, QComboBox):
                if tipo_combo.findText(tipo) < 0:
                    tipo_combo.addItem(tipo)
                with QSignalBlocker(tipo_combo):
                    tipo_combo.setCurrentText(tipo)

            # Fase
            fase = str(d.get("fase", "1F"))
            fase_combo = self.table.cellWidget(row, COL_FASE)
            if isinstance(fase_combo, QComboBox):
                if fase_combo.findText(fase) < 0:
                    fase_combo.addItem(fase)
                with QSignalBlocker(fase_combo):
                    fase_combo.setCurrentText(fase)

            usar_va = bool(d.get("usar_va"))
            self._apply_power_mode_to_row(row, usar_va, tipo)
        finally:
            self._loading = prev

    def _get_checkbox_at(self, row: int, col: int) -> QCheckBox | None:
        w = self.table.cellWidget(row, col)
        if isinstance(w, QCheckBox):
            return w
        if w is None:
            return None
        return w.findChild(QCheckBox)

    def _set_checkbox_checked_safely(self, chk: QCheckBox, checked: bool):
        prev = chk.blockSignals(True)
        chk.setChecked(checked)
        chk.blockSignals(prev)

    def _apply_origin_to_row(self, row: int, origen: str):
        with self._ui_update():
            # Localizar componente y sus datos
            comp_id = self._get_comp_id_by_row(row)
            comp = None
            if comp_id and self.current_cabinet:
                for c in self.current_cabinet.get("components", []):
                    if c.get("id") == comp_id:
                        comp = c
                        break

            data = self._normalize_comp_data(comp.get("data", {})) if comp else {}
            base_name = comp.get("base", "") if comp else ""

            # Habilitar "Alimentador" solo cuando el origen sea "Por Usuario"
            alimentador_combo = self.table.cellWidget(row, COL_ALIMENTADOR)
            if isinstance(alimentador_combo, QComboBox):
                alimentador_combo.setEnabled(origen == "Por Usuario")

            # Limpiar cualquier widget previo en Marca/Modelo
            for col in (COL_MARCA, COL_MODELO):
                widget = self.table.cellWidget(row, col)
                if widget is not None:
                    widget.deleteLater()
                    self.table.setCellWidget(row, col, None)

            # ---------- ORIGEN: POR USUARIO (marca y modelo editables) ----------
            if origen == "Por Usuario":
                for col, key in ((COL_MARCA, "marca"), (COL_MODELO, "modelo")):
                    self._set_cell_editable(row, col, True)
                    item = self._ensure_item(row, col, "")
                    txt = data.get(key, "")
                    item.setText("" if not txt else txt)

            # ---------- ORIGEN: SEGÚN FABRICANTE (combos filtrados) ----------
            elif origen == "Según Fabricante":
                variants = self._get_db_variants_for(base_name)
                if not variants:
                    origen = "Genérico"  # sin base -> tratamos como genérico
                else:
                    brand_combo = QComboBox(self.table)
                    model_combo = QComboBox(self.table)

                    marcas = sorted(
                        {v.get("marca", "") for v in variants if v.get("marca", "")}
                    )
                    brand_combo.addItem("")
                    for m in marcas:
                        brand_combo.addItem(m)

                    self.table.setCellWidget(row, COL_MARCA, brand_combo)
                    self.table.setCellWidget(row, COL_MODELO, model_combo)

                    # Items "fantasma" para mostrar texto pero no editar
                    for col, key in ((COL_MARCA, "marca"), (COL_MODELO, "modelo")):
                        self._set_cell_editable(row, col, False)
                        item = self._ensure_item(row, col, "")
                        txt = data.get(key, "")
                        item.setText("" if not txt else txt)

                    def refresh_models(selected_brand: str, keep_model: str = ""):
                        with QSignalBlocker(model_combo):
                            model_combo.clear()
                            models = [
                                v for v in variants
                                if v.get("marca", "") == selected_brand
                            ]
                            model_combo.addItem("")
                            for v in models:
                                model_text = v.get("modelo", "")
                                model_combo.addItem(model_text, userData=v)
                            if keep_model:
                                idx = model_combo.findText(keep_model)
                                if idx >= 0:
                                    model_combo.setCurrentIndex(idx)

                    marca_ini = data.get("marca", "")
                    modelo_ini = data.get("modelo", "")
                    if marca_ini and marca_ini in marcas:
                        with QSignalBlocker(brand_combo):
                            brand_combo.setCurrentText(marca_ini)
                        refresh_models(marca_ini, modelo_ini)
                    else:
                        refresh_models("")

                    def on_brand_changed(text: str, cid=comp_id):
                        if self._ui_updating():
                            return
                        self._sync_from_table(cid, "marca", text)
                        item_marca = self._ensure_item(row, COL_MARCA, "")
                        item_marca.setText(text or "")
                        refresh_models(text)

                    def on_model_changed(index: int, cid=comp_id):
                        if self._ui_updating():
                            return
                        comp_data = model_combo.itemData(index)
                        model_text = model_combo.currentText()
                        self._sync_from_table(cid, "modelo", model_text)
                        item_modelo = self._ensure_item(row, COL_MODELO, "")
                        item_modelo.setText(model_text or "")

                        # Completar datos desde base (potencias, tipo, fase, etc.)
                        if isinstance(comp_data, dict):
                            for k in ("potencia_w", "potencia_va",
                                      "usar_va", "tipo_consumo", "fase"):
                                if k in comp_data:
                                    self._sync_from_table(cid, k, comp_data[k])
                            row_idx = self.row_by_id.get(cid)
                            if row_idx is not None:
                                self._update_row_from_data(row_idx, comp_data)

                    brand_combo.currentTextChanged.connect(on_brand_changed)
                    model_combo.currentIndexChanged.connect(on_model_changed)

            # ---------- ORIGEN: GENÉRICO (marca/modelo bloqueados "----") ----------
            if origen == "Genérico":
                for col in (COL_MARCA, COL_MODELO):
                    self._set_cell_editable(row, col, False)
                    item = self._ensure_item(row, col, "")
                    item.setText("----")

            # ---------- SIEMPRE: volver a aplicar reglas de potencia ----------
            chk = self._get_checkbox_at(row, COL_USAR_VA)
            usar_va = bool(chk.isChecked()) if chk is not None else False
            tipo = self._combo_text_at(row, COL_TIPO)
            self._apply_power_mode_to_row(row, usar_va, tipo)

    def _apply_power_mode_to_row(self, row: int, usar_va: bool, tipo_consumo: str):
        with self._ui_update():
            item_w = self._ensure_item(row, COL_P_W, "")
            item_va = self._ensure_item(row, COL_P_VA, "")

            flags_w = item_w.flags()
            flags_va = item_va.flags()

            chk = self._get_checkbox_at(row, COL_USAR_VA)
            fase_combo = self.table.cellWidget(row, COL_FASE)

            origen = self._combo_text_at(row, COL_ORIGEN)
            is_user_origin = (origen == "Por Usuario")

            disabled_brush = QBrush(QColor(get_theme_token("INPUT_DISABLED_BG", "#E6E6E6")))
            normal_brush = QBrush(QColor(get_theme_token("SURFACE", "#FFFFFF")))

            # Reset visual básico
            item_w.setBackground(normal_brush)
            item_va.setBackground(normal_brush)

            # =====================================================
            # 1) ORIGEN ≠ "POR USUARIO"  -> POTENCIAS SIEMPRE FIJAS
            # =====================================================
            if not is_user_origin:
                if chk is not None:
                    self._set_checkbox_checked_safely(chk, False)
                    chk.setEnabled(False)

                # Fase sólo deshabilitada para C.C.
                if tipo_consumo.startswith("C.C."):
                    if fase_combo:
                        fase_combo.setEnabled(False)
                else:
                    if fase_combo:
                        fase_combo.setEnabled(True)

                item_w.setFlags(flags_w & ~Qt.ItemIsEditable)
                item_va.setFlags(flags_va & ~Qt.ItemIsEditable)
                item_w.setBackground(disabled_brush)
                item_va.setBackground(disabled_brush)
                return

            # =====================================================
            # 2) ORIGEN "POR USUARIO" -> reglas normales
            # =====================================================
            if chk is not None:
                chk.setEnabled(True)

            # Helper local para leer valor numérico si existe
            def _num(text):
                text = (text or "").strip()
                if text in ("", "----"):
                    return None
                try:
                    return float(text)
                except ValueError:
                    return None

            # ----- Consumo C.C. -----
            if tipo_consumo.startswith("C.C."):
                if chk is not None:
                    self._set_checkbox_checked_safely(chk, False)

                if fase_combo:
                    fase_combo.setEnabled(False)

                item_va.setText("----")
                item_va.setFlags(flags_va & ~Qt.ItemIsEditable)
                item_va.setBackground(disabled_brush)

                item_w.setFlags(flags_w | Qt.ItemIsEditable)
                item_w.setBackground(normal_brush)
                if item_w.text() == "----":
                    item_w.setText("")
                return

            # ----- Consumo C.A. -----
            if fase_combo:
                fase_combo.setEnabled(True)

            # Leemos valores actuales antes de cambiar flags
            val_w = _num(item_w.text())
            val_va = _num(item_va.text())

            if usar_va:
                # Queremos dejar VA activo. Si VA no tiene valor, usamos el de W.
                value = val_va if val_va is not None else val_w

                item_va.setFlags(flags_va | Qt.ItemIsEditable)
                if value is not None:
                    item_va.setText(str(value))
                elif item_va.text() == "----":
                    item_va.setText("")

                item_w.setText("----")
                item_w.setFlags(flags_w & ~Qt.ItemIsEditable)
                return

            # Queremos dejar W activo. Si W no tiene valor, usamos el de VA.
            value = val_w if val_w is not None else val_va

            item_w.setFlags(flags_w | Qt.ItemIsEditable)
            if value is not None:
                item_w.setText(str(value))
            elif item_w.text() == "----":
                item_w.setText("")

            item_va.setText("----")
            item_va.setFlags(flags_va & ~Qt.ItemIsEditable)

    def _on_origin_changed(self, _index: int):
        if self._ui_updating() or getattr(self, "_loading", False):
            return
        combo = self.sender()
        if not isinstance(combo, QComboBox):
            return
        comp_id = combo.property("comp_id")
        if not comp_id:
            return
        value = combo.currentText()
        self._begin_user_edit()
        try:
            self._controller.sync_from_table(comp_id, "origen", value)
        finally:
            self._end_user_edit()

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if getattr(self, "_loading", False) or self._ui_updating():
            return
        self._begin_user_edit()
        try:
            return self._controller.on_table_item_changed(item)
        finally:
            self._end_user_edit()

    def _sync_from_table(self, comp_id: str, key: str, value):
        if getattr(self, "_loading", False) or self._ui_updating():
            return
        self._begin_user_edit()
        try:
            return self._controller.sync_from_table(comp_id, key, value)
        finally:
            self._end_user_edit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete and self.current_cabinet:
            selected = [it for it in self.scene.selectedItems() if isinstance(it, ComponentCardItem)]
            if selected:
                for it in selected:
                    self.remove_component_item(it)
                event.accept()
                return
        super().keyPressEvent(event)


    # ---- ScreenBase hooks / UI state ----
    def load_from_model(self):
        """Load current project data into this screen."""
        try:
            # These are safe idempotent loads.
            self.load_cabinets()
            self.load_equipment()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def commit_pending_edits(self):
        """Force commit of the active editor to avoid losing edits on tab switch."""
        if not hasattr(self, "table") or self.table is None:
            return
        try:
            from PyQt5.QtWidgets import QApplication, QAbstractItemDelegate, QAbstractItemView

            app = QApplication.instance()
            if app is None:
                return
            if self.table.state() == QAbstractItemView.EditingState:
                editor = app.focusWidget()
                try:
                    self.table.closeEditor(editor, QAbstractItemDelegate.SubmitModelCache)
                except Exception:
                    import logging
                    logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
            try:
                app.processEvents()
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def save_to_model(self):
        # This screen writes changes through table/drag handlers.
        self.commit_pending_edits()
        return

    # --- Equipment tree integration (overrides legacy flat-list loader) ---
    def load_equipment(self):
        # Preferimos la libreria de consumos cargada (consumos.lib)
        lib = getattr(self.data_model, "library_data", {}).get("consumos")
        items = []
        if isinstance(lib, dict) and lib.get("file_type") == "SSAA_LIB_CONSUMOS":
            raw_items = lib.get("items", [])
            if isinstance(raw_items, list):
                items = [it for it in raw_items if isinstance(it, dict)]
        else:
            items = self._load_component_database()

        tree_items = []
        seen = set()
        for comp in items:
            if not isinstance(comp, dict):
                continue
            name = str(comp.get("name", "")).strip()
            lib_uid = str(comp.get("lib_uid", "") or "").strip()
            code = str(comp.get("code", "") or "").strip()
            norm = " ".join(name.split()).casefold()
            if not norm or norm in seen:
                continue
            seen.add(norm)

            d = self._normalize_comp_data(dict(comp))
            tree_items.append(
                {
                    "name": name,
                    "lib_uid": lib_uid,
                    "code": code,
                    "tipo_consumo": str(d.get("tipo_consumo", "C.C. permanente") or "C.C. permanente"),
                    "origen": str(d.get("origen", "Generico") or "Generico"),
                }
            )

        if not tree_items:
            defaults = [
                "Controlador",
                "Proteccion Sistema 1",
                "Proteccion Sistema 2",
                "Proteccion 50BF",
                "Proteccion 87B",
                "Equipo de Facturacion",
                "Switch de Comunicaciones",
                "Reloj GPS",
                "RTU",
                "HMI",
                "Redbox",
                "Reles Auxiliares",
                "Luz Indicadora",
            ]
            for name in defaults:
                tree_items.append(
                    {
                        "name": name,
                        "lib_uid": "",
                        "code": "",
                        "tipo_consumo": "C.C. permanente",
                        "origen": "Generico",
                    }
                )

        self.equipment_tree.set_items(tree_items)

    def _add_equipment_to_cabinet(self, payload: dict):
        if not isinstance(payload, dict):
            return
        name = str(payload.get("name", "")).strip()
        if not name:
            return
        lib_uid = str(payload.get("lib_uid", "") or "")
        code = str(payload.get("code", "") or "")
        self.add_component_at(name, QPointF(0, 0), lib_uid=lib_uid, code=code)

    def closeEvent(self, event):
        try:
            if hasattr(self, "table") and self.table is not None:
                save_header_state(self.table.horizontalHeader(), "cabinet.components.table.header")
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
        return super().closeEvent(event)
