# -*- coding: utf-8 -*-
"""screens/ssaa_designer/screen.py

Diseñador (tipo DUF/CAD) para arquitectura de Servicios Auxiliares.

Objetivo:
- Permitir construir un esquema (nodos + conexiones) para CA y CC, reutilizando como
  "fuente de verdad" los requerimientos definidos en la pestaña "Alimentación tableros".
- Mostrar issues básicos por capa (CA o CC+Sistema DC).
- Construir en tiempo real un cuadro de cargas simple (suma aguas abajo por tablero).

Notas:
- Este módulo es 100% UI PyQt5.
- La persistencia se guarda en proyecto[ProjectKeys.SSAA_TOPOLOGY_LAYERS] dentro del DataModel.
"""

from __future__ import annotations

from .context_actions import connect_nodes_checked, auto_connect_orphans_interactive, connect_from_context
from .workspace_tabs import rebuild_workspace_tabs, available_workspaces, on_workspace_tab_changed, sync_layer_label
from .feeders import iter_feed_rows, refresh_feeders, refresh_feeders_table, drop_feeder_on_canvas
from .sources import iter_source_rows, refresh_sources_table, drop_source_on_canvas
from .boards import iter_board_rows, refresh_boards_table, drop_board_on_canvas



def safe_slot(fn):
    """Decorator to prevent uncaught exceptions in Qt slots from crashing the app."""
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error", f"{fn.__name__}: {e}")
            except Exception:
                import logging
                logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
            return None
    return wrapper
import uuid
from typing import Dict, List, Optional, Tuple

from domain.ssaa_topology import TopoNode, TopoEdge, to_float

from .ssaa_designer_controller import SSaaDesignerController
from .graphics import GRID, TopoNodeItem, PortItem, TopoEdgeItem, TopoView
from .graphics.port_layout import compute_node_width
from .graphics.layout_constants import CARD_WIDTH, CARD_GAP, SIDE_PADDING
from .graphics.auto_layout import auto_place_children


from screens.base import ScreenBase
from app.sections import Section
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPainterPath
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsPathItem,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QInputDialog, QGroupBox, QListWidget, QDialog
)


from .widgets.exports import LoadTableDialog, FeedListWidget, build_issues_panel, build_feeders_panel, build_sources_panel, build_boards_panel

def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _norm_txt(s: str) -> str:
    return (s or "").strip()


### NOTE:
# Los modelos TopoNode/TopoEdge viven en domain.ssaa_topology (sin dependencias Qt).


# (moved) LoadTableDialog
# (moved) FeedListWidget
class SSAADesignerScreen(ScreenBase):
    SECTION = Section.DESIGNER
    """Pestaña: diseñador de arquitectura SS/AA."""

    def __init__(self, data_model, parent=None):
        super().__init__(data_model, parent=parent)
        self.data_model = data_model

        # Controller (orquestación + persistencia). Se crea temprano para que
        # cualquier llamada a _persist/_topo_store durante init no falle.
        self._controller = SSaaDesignerController(self)
        from PyQt5.QtCore import QTimer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh_on_external_change)

        self._connect_mode = False
        self._connect_first: Optional[str] = None
        self._connect_circuit = "CA"
        self._connect_dc_system = "B1"

        self._pending_port: Optional[Tuple[str, str]] = None
        self._auto_place_children = False

        self._node_items: Dict[str, TopoNodeItem] = {}
        self._edge_items: Dict[str, TopoEdgeItem] = {}

        self._last_layer_issues: List[Dict] = []
        self._last_issue_layer: Dict = {"circuit": "CA", "dc": ""}

        self._build_ui()
        self._refresh_issues_layer_combo()

        # Startup-safe: avoid loading/validating topology during __init__.
        # The SectionOrchestrator will call load_from_model()/reload_from_project()
        # on project load / relevant changes.
        try:
            self.enter_safe_state()
        except Exception:
            pass
        if hasattr(self.data_model, "on"):
            self.data_model.on("section_changed", self._on_section_changed)

    def load_from_model(self):
        """Populate UI from current DataModel (ScreenBase hook)."""
        self.reload_from_project()

    def enter_safe_state(self) -> None:
        """Initialize an empty canvas/state without touching the model."""
        try:
            # Ensure we have a scene and views already built.
            if hasattr(self, 'scene'):
                self.scene.clear()
            if hasattr(self, 'lst_issues'):
                self.lst_issues.clear()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        # La pestaña 'Alimentación tableros' puede cambiar después; recalculamos workspaces
        try:
            self._rebuild_workspace_tabs()
            # Refrescar alimentadores (incluye consumos con alimentador 'Individual')
            self._refresh_feeders_table()
            self._refresh_boards_table()
            self._refresh_sources_table()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    # ---------------- storage ----------------
    def _topo_store(self) -> Dict:
        """Devuelve el store de topología para la pestaña/capa actual."""
        return self._controller.topo_store()

    def _persist(self):
        """Persistir nodos/aristas actuales al proyecto (DataModel)."""
        return self._controller.persist()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        # -------------------------------------------------
        # "Pestañas" de espacio de trabajo (tipo AutoCAD)
        # Se crean según lo marcado en "Alimentación tableros"
        # -------------------------------------------------
        from PyQt5.QtWidgets import QTabWidget
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self._workspace_tabs = []  # [(workspace_key, tab_index)]
        self._rebuild_workspace_tabs()
        # Refrescar alimentadores (incluye consumos con alimentador 'Individual')
        self._refresh_feeders_table()
        # Cambio de pestaña = cambio de workspace (capa de trabajo)
        self.tabs.currentChanged.connect(self._on_workspace_tab_changed)

        # -------------------------------------------------
        # Cuerpo: izquierda (issues + canvas) / derecha (alimentadores)
        # -------------------------------------------------
        split = QSplitter(Qt.Horizontal)
        root.addWidget(split, 1)

        # LEFT: Issues (arriba) + Canvas (abajo)
        left_split = QSplitter(Qt.Vertical)

        left_split.addWidget(build_issues_panel(self))

        # Canvas
        self.scene = QGraphicsScene(self)
        self.view = TopoView(
            self.scene,
            on_delete_selected=self._delete_selected,
            on_drop_feeder=self._drop_feeder_on_canvas,
            on_drop_source=self._drop_source_on_canvas,
            on_drop_board=self._drop_board_on_canvas,
        )
        self.view.setSceneRect(0, 0, 2400, 1400)
        left_split.addWidget(self.view)
        left_split.setStretchFactor(0, 1)
        left_split.setStretchFactor(1, 3)

        split.addWidget(left_split)

        # RIGHT: Alimentadores, Tableros/Fuentes y Fuentes disponibles (drag&drop)
        right = QWidget()
        vright = QVBoxLayout(right)
        vright.addWidget(build_feeders_panel(self), 1)
        vright.addWidget(build_boards_panel(self), 1)
        vright.addWidget(build_sources_panel(self), 1)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)

        self.setLayout(root)

        self.scene.selectionChanged.connect(self.on_selection_changed)

        # inicial
        self._sync_layer_label()
        self._refresh_feeders_table()
        self._refresh_boards_table()
        self._refresh_sources_table()
        self._refresh_boards_table()
        self._refresh_sources_table()
    def _refresh_dc_systems_combo(self, *args, **kwargs):
        return

    def _apply_circuit_ui_state(self, *args, **kwargs):
        return

    def _rebuild_workspace_tabs(self):
        return rebuild_workspace_tabs(self)

    def _available_workspaces(self) -> List[str]:
        return available_workspaces(self)

    @safe_slot
    def _on_workspace_tab_changed(self, idx: int):
        return on_workspace_tab_changed(self, idx)

    def _sync_layer_label(self):
        return sync_layer_label(self)

    def _iter_feed_rows(self):
        return iter_feed_rows(self)

    def _iter_source_rows(self):
        return iter_source_rows(self)

    def _iter_board_rows(self):
        return iter_board_rows(self)

    def _refresh_feeders(self):
        return refresh_feeders(self)

    def _refresh_feeders_table(self):
        return refresh_feeders_table(self)

    def _refresh_sources(self):
        return refresh_sources_table(self)

    def _refresh_sources_table(self):
        return refresh_sources_table(self)

    def _refresh_boards(self):
        return refresh_boards_table(self)

    def _refresh_boards_table(self):
        return refresh_boards_table(self)

    def _drop_source_on_canvas(self, scene_pos: QPointF, source: Dict):
        return drop_source_on_canvas(self, scene_pos, source)

    def _drop_board_on_canvas(self, scene_pos: QPointF, board: Dict):
        return drop_board_on_canvas(self, scene_pos, board)

    def _add_selected_feeders_as_nodes(self):
        QMessageBox.information(self, "Cargas", "Usa drag & drop desde la lista para crear nodos de carga.")


    # ======================================================
    # Public API (used by widgets / controller / signals)
    # Keep these method names stable to avoid startup crashes during refactors.
    # ======================================================

    def refresh_issues(self):
        """Stable public API to refresh the issues panel/list."""
        if hasattr(self, "_refresh_issues_panel") and callable(getattr(self, "_refresh_issues_panel")):
            return self._refresh_issues_panel()
        return None

    def auto_connect_orphans(self):
        """Stable public API to auto-connect orphan nodes (interactive)."""
        if hasattr(self, "_auto_connect_orphans_interactive") and callable(getattr(self, "_auto_connect_orphans_interactive")):
            return self._auto_connect_orphans_interactive()
        return None

    def refresh_feeders(self):
        """Stable public API to refresh feeders list."""
        if hasattr(self, "_refresh_feeders") and callable(getattr(self, "_refresh_feeders")):
            return self._refresh_feeders()
        return None

    def refresh_sources(self):
        """Stable public API to refresh sources list."""
        if hasattr(self, "_refresh_sources") and callable(getattr(self, "_refresh_sources")):
            return self._refresh_sources()
        return None

    def refresh_boards(self):
        """Stable public API to refresh boards list."""
        if hasattr(self, "_refresh_boards") and callable(getattr(self, "_refresh_boards")):
            return self._refresh_boards()
        return None

    def order_diagram(self):
        """Stable public API to auto-order current layer."""
        if hasattr(self, "_order_diagram") and callable(getattr(self, "_order_diagram")):
            return self._order_diagram()
        return None

    def _on_section_changed(self, section):
        if section in (Section.BOARD_FEED, Section.CABINET, Section.INSTALACIONES):
            if self._refresh_timer.isActive():
                self._refresh_timer.start(250)
            else:
                self._refresh_timer.start(250)

    def _refresh_on_external_change(self):
        try:
            self._refresh_feeders_table()
            self._refresh_boards_table()
            self._refresh_sources_table()
            self._refresh_issues_panel()
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def _order_diagram(self):
        """Auto-order nodes in the current layer (deterministic BFS layout)."""
        if not self._node_items:
            return

        nodes = list(self._node_items.values())
        edges = [it.edge for it in self._edge_items.values()]

        indeg: Dict[str, int] = {n.node.id: 0 for n in nodes}
        adj: Dict[str, List[str]] = {n.node.id: [] for n in nodes}
        for e in edges:
            if e.src in adj and e.dst in indeg:
                adj[e.src].append(e.dst)
                indeg[e.dst] += 1

        def _is_root(nit: TopoNodeItem) -> bool:
            k = (nit.node.kind or "").upper()
            if k == "FUENTE":
                return True
            if (nit.node.meta or {}).get("root_board"):
                return True
            return indeg.get(nit.node.id, 0) == 0

        roots = [n for n in nodes if _is_root(n)]
        rest = [n for n in nodes if n not in roots]

        level: Dict[str, int] = {}
        queue = [n.node.id for n in roots]
        for rid in queue:
            level[rid] = 0

        while queue:
            u = queue.pop(0)
            for v in adj.get(u, []):
                if v not in level:
                    level[v] = level[u] + 1
                    queue.append(v)

        # Unreachable nodes -> append after last level
        max_level = max(level.values()) if level else 0
        for n in rest:
            if n.node.id not in level:
                max_level += 1
                level[n.node.id] = max_level

        # Group by level, stable order by tag/name
        by_level: Dict[int, List[TopoNodeItem]] = {}
        for nit in nodes:
            lvl = level.get(nit.node.id, 0)
            by_level.setdefault(lvl, []).append(nit)

        for lvl in by_level:
            by_level[lvl].sort(key=lambda it: ((it.node.meta or {}).get("tag") or it.node.name or it.node.id))

        dx = 340.0
        dy = 140.0
        start_x = 60.0
        start_y = 60.0

        self.scene.blockSignals(True)
        try:
            self._sync_board_ports(align_children=False)
            for lvl in sorted(by_level.keys()):
                col = by_level[lvl]
                for idx, nit in enumerate(col):
                    x = start_x + lvl * dx
                    y = start_y + idx * dy
                    x = round(x / GRID) * GRID
                    y = round(y / GRID) * GRID
                    nit.setPos(QPointF(x, y))
                    nit.node.pos = (float(x), float(y))
        finally:
            self.scene.blockSignals(False)

        self._persist()
        self._rebuild_all_edges()

        # Align children to board output ports (straight edges)
        self._sync_board_ports(align_children=True)
        edges = [it.edge for it in self._edge_items.values()]
        for nit in self._node_items.values():
            if (nit.node.kind or "").upper().startswith(("TG", "TD", "TDA")):
                auto_place_children(nit, edges, self._node_items, only_unpinned=True)
        self._persist()
        self._rebuild_all_edges()

    def _sync_board_ports(self, align_children: bool) -> None:
        """Ensure dynamic IN/OUT ports for boards and (optionally) align children to port columns."""
        nodes = list(self._node_items.values())
        edges = [it.edge for it in self._edge_items.values()]

        adj_out: Dict[str, List[str]] = {}
        adj_in: Dict[str, List[str]] = {}
        for e in edges:
            adj_out.setdefault(e.src, []).append(e.dst)
            adj_in.setdefault(e.dst, []).append(e.src)

        changed = False
        for nit in nodes:
            kind = (nit.node.kind or "").upper()
            if not kind.startswith(("TG", "TD", "TDA")):
                continue

            meta = nit.node.meta or {}
            ui = meta.get("ui")
            if not isinstance(ui, dict):
                ui = {}
            out_map = ui.get("out_port_map")
            in_map = ui.get("in_port_map")
            if not isinstance(out_map, dict):
                out_map = {}
            if not isinstance(in_map, dict):
                in_map = {}
            desired_in = int(ui.get("desired_in_ports") or 1)
            desired_out = int(ui.get("desired_out_ports") or 1)

            def _next_free_index(m: dict) -> int:
                used = {int(v) for v in m.values() if isinstance(v, int) or str(v).isdigit()}
                i = 0
                while i in used:
                    i += 1
                return i

            for child_id in adj_out.get(nit.node.id, []):
                if str(child_id) not in out_map:
                    out_map[str(child_id)] = _next_free_index(out_map)
                    changed = True
            for parent_id in adj_in.get(nit.node.id, []):
                if str(parent_id) not in in_map:
                    in_map[str(parent_id)] = _next_free_index(in_map)
                    changed = True

            needed_out = (max(out_map.values()) + 1) if out_map else 1
            needed_in = (max(in_map.values()) + 1) if in_map else 1
            n_out = max(1, needed_out, desired_out)
            n_in = max(1, needed_in, desired_in)

            existing_ports = meta.get("ports", []) or []
            existing_in = [p for p in existing_ports if (p.get("io") or "").upper() == "IN"]
            existing_out = [p for p in existing_ports if (p.get("io") or "").upper() == "OUT"]
            n_in = max(n_in, len(existing_in))
            n_out = max(n_out, len(existing_out))

            board_w = compute_node_width(kind, n_in, n_out)
            force_layout = False
            if ui.get("w") != int(board_w):
                ui["w"] = int(board_w)
                changed = True
                force_layout = True
            ui.setdefault("expanded", True)
            ui["desired_in_ports"] = desired_in
            ui["desired_out_ports"] = desired_out
            ui["out_port_map"] = out_map
            ui["in_port_map"] = in_map
            if ui.get("last_n_in") != n_in:
                ui["last_n_in"] = int(n_in)
                force_layout = True
            if ui.get("last_n_out") != n_out:
                ui["last_n_out"] = int(n_out)
                force_layout = True
            meta["ui"] = ui
            nit.node.meta = meta
            if abs(nit.node.size[0] - board_w) > 0.5:
                old_w = nit.node.size[0]
                center_x = nit.node.pos[0] + old_w / 2.0
                nit.node.size = (float(board_w), float(nit.node.size[1]))
                nit.setPos(QPointF(center_x - board_w / 2.0, nit.pos().y()))

            ports = existing_ports
            out_port_ids: Dict[int, str] = {}
            in_port_ids: Dict[int, str] = {}
            for e in edges:
                if e.src == nit.node.id:
                    idx = out_map.get(str(e.dst))
                    if idx is not None:
                        pid = (e.meta or {}).get("src_port")
                        if pid:
                            out_port_ids[int(idx)] = str(pid)
                if e.dst == nit.node.id:
                    idx = in_map.get(str(e.src))
                    if idx is not None:
                        pid = (e.meta or {}).get("dst_port")
                        if pid:
                            in_port_ids[int(idx)] = str(pid)

            def _find_port_id(io: str, idx: int) -> str:
                name = io if idx == 0 else f"{io}{idx+1}"
                for p in ports:
                    if (p.get("io") or "").upper() == io and str(p.get("name") or "") == name:
                        return str(p.get("id") or "")
                return ""

            new_ports = []
            for i in range(n_in):
                pid = in_port_ids.get(i) or _find_port_id("IN", i) or _new_id("p")
                name = "IN" if i == 0 else f"IN{i+1}"
                new_ports.append({"id": pid, "name": name, "io": "IN", "side": "top", "x": None})
            for i in range(n_out):
                pid = out_port_ids.get(i) or _find_port_id("OUT", i) or _new_id("p")
                name = "OUT" if i == 0 else f"OUT{i+1}"
                new_ports.append({"id": pid, "name": name, "io": "OUT", "side": "bottom", "x": None})

            # Preserve extra manual ports (do not delete).
            used_ids = {p["id"] for p in new_ports}
            for p in ports:
                pid = str(p.get("id") or "")
                if pid and pid not in used_ids:
                    new_ports.append(p)

            meta["ports"] = new_ports
            nit.node.meta = meta
            nit._rebuild_ports()
            nit._layout_ports(force=force_layout)

            # Update edges to use current port ids for stable attachment
            out_port_ids = {int(i): p["id"] for i, p in enumerate([p for p in new_ports if p["io"] == "OUT"])}
            in_port_ids = {int(i): p["id"] for i, p in enumerate([p for p in new_ports if p["io"] == "IN"])}
            for e in edges:
                if e.src == nit.node.id:
                    idx = out_map.get(str(e.dst))
                    if idx is not None:
                        e.meta = dict(e.meta or {})
                        e.meta["src_port"] = out_port_ids.get(int(idx))
                if e.dst == nit.node.id:
                    idx = in_map.get(str(e.src))
                    if idx is not None:
                        e.meta = dict(e.meta or {})
                        e.meta["dst_port"] = in_port_ids.get(int(idx))

            if align_children:
                base_x = nit.node.pos[0]
                pad_l = SIDE_PADDING
                port_pitch = CARD_WIDTH + CARD_GAP
                for child_id, idx in out_map.items():
                    child_item = self._node_items.get(child_id)
                    if child_item is None:
                        continue
                    port_x = base_x + pad_l + idx * port_pitch + (CARD_WIDTH / 2.0)
                    child_w = float(child_item.node.size[0])
                    child_x = port_x - (child_w / 2.0)
                    child_x = round(child_x / GRID) * GRID
                    child_item.setPos(QPointF(child_x, child_item.pos().y()))
                    child_item.node.pos = (float(child_x), float(child_item.pos().y()))

        if changed:
            self._ports_migrated = True


    def on_selection_changed(self):
        """Stable public handler for scene selection changes."""
        _h = getattr(self, "_on_selection_changed", None)
        if callable(_h):
            _h()

    def _on_ports_changed(self, node_id: str):
        """Se llamó al agregar puertos. Recalcula aristas y persiste."""
        # Pipeline centralizado (3C.8)
        self._controller.after_topology_mutation(
            rebuild_edges=True,
            recompute_load_table=False,
            refresh_feeders=False,
            refresh_issues=True,
        )

    def _drop_feeder_on_canvas(self, scene_pos: QPointF, feeder: Dict):
        return drop_feeder_on_canvas(self, scene_pos, feeder)

    def _add_node_item(self, node: TopoNode):
        item = TopoNodeItem(node, on_moved=self._on_node_moved, on_connect_from=self._connect_from_context, on_port_clicked=self._on_port_clicked, on_port_added=self._on_ports_changed)
        self._node_items[node.id] = item
        self.scene.addItem(item)
        if getattr(item, "_ports_changed", False):
            self._ports_migrated = True
        if getattr(item, "_ui_changed", False):
            self._ui_migrated = True
        return item

    def _add_edge_item(self, edge: TopoEdge):
        src = self._node_items.get(edge.src)
        dst = self._node_items.get(edge.dst)
        if src is None or dst is None:
            return None
        it = TopoEdgeItem(edge, src, dst)
        self._edge_items[edge.id] = it
        self.scene.addItem(it)
        return it

    def _delete_selected(self):
        selected = list(self.scene.selectedItems())
        if not selected:
            return

        to_del_edges: List[str] = []
        to_del_nodes: List[str] = []
        for it in selected:
            if isinstance(it, TopoEdgeItem):
                to_del_edges.append(it.edge.id)
            elif isinstance(it, TopoNodeItem):
                to_del_nodes.append(it.node.id)

        # si borro nodos, borro aristas asociadas
        if to_del_nodes:
            for eid, eit in list(self._edge_items.items()):
                if eit.edge.src in to_del_nodes or eit.edge.dst in to_del_nodes:
                    to_del_edges.append(eid)

        for eid in set(to_del_edges):
            eit = self._edge_items.pop(eid, None)
            if eit is not None:
                self.scene.removeItem(eit)

        # Si se eliminan nodos que provienen de la lista de alimentadores (drag&drop),
        # liberar su "consumo" para que vuelvan a aparecer en la lista.
        topo = self._topo_store()
        used = set(topo.get("used_feeders", []) or [])

        for nid in set(to_del_nodes):
            nit = self._node_items.pop(nid, None)
            if nit is not None:
                fk = (nit.node.meta or {}).get("feeder_key")
                if fk:
                    used.discard(str(fk))
                self.scene.removeItem(nit)

        topo["used_feeders"] = sorted(used)

        # Persist + refrescos (pipeline)
        self._controller.after_topology_mutation(
            rebuild_edges=True,
            recompute_load_table=True,
            refresh_feeders=True,
            refresh_issues=True,
        )

    def _rebuild_all_edges(self):
        self._sync_board_ports(align_children=False)
        for e in self._edge_items.values():
            e.rebuild()

    def _rebuild_edges_only(self):
        for e in self._edge_items.values():
            e.rebuild()

    def _assign_edge_lane(self, edge: TopoEdge) -> None:
        meta = dict(edge.meta or {})
        if meta.get("lane_x") is not None:
            edge.meta = meta
            return
        src_item = self._node_items.get(edge.src)
        if src_item is None:
            return
        sp = meta.get("src_port")
        if sp:
            base_x = src_item.port_scene_pos(str(sp)).x()
        else:
            r = src_item.boundingRect()
            base_x = src_item.pos().x() + r.width() / 2.0

        used = []
        for it in self._edge_items.values():
            e = it.edge
            if e.src != edge.src:
                continue
            lx = (e.meta or {}).get("lane_x")
            try:
                used.append(float(lx))
            except Exception:
                continue

        gap = 20.0
        lane_x = base_x
        if used:
            def _conflicts(x: float) -> bool:
                return any(abs(x - u) < gap for u in used)
            if _conflicts(lane_x):
                for k in range(1, 50):
                    for sign in (1.0, -1.0):
                        cand = base_x + sign * k * gap
                        if not _conflicts(cand):
                            lane_x = cand
                            break
                    if not _conflicts(lane_x):
                        break
        meta["lane_x"] = float(lane_x)
        edge.meta = meta

    def _ensure_edge_lanes(self) -> None:
        changed = False
        for it in self._edge_items.values():
            e = it.edge
            if (e.meta or {}).get("lane_x") is None:
                self._assign_edge_lane(e)
                changed = True
        if changed:
            self._persist()

    # ---------------- load/persist ----------------


    def load_from_model(self):
        # ScreenBase hook: recargar vista desde el proyecto
        self.reload_from_project()

    def save_to_model(self):
        # ScreenBase hook: persistir estado actual al proyecto
        self._persist()

    def reload_from_project(self):
        # Cargar/recuperar topología de la capa actual (workspace)
        if not hasattr(self, "scene"):
            return

        self.scene.blockSignals(True)
        try:
            self._ports_migrated = False
            self._ui_migrated = False
            self.scene.clear()
            self._node_items.clear()
            self._edge_items.clear()

            topo = self._topo_store()
            nodes = [TopoNode.from_dict(d) for d in (topo.get("nodes", []) or [])]
            edges = [TopoEdge.from_dict(d) for d in (topo.get("edges", []) or [])]

            for n in nodes:
                self._add_node_item(n)

            for e in edges:
                self._add_edge_item(e)
        finally:
            self.scene.blockSignals(False)

        self._sync_layer_label()
        self._refresh_feeders_table()
        self._sync_board_ports(align_children=False)
        self._ensure_edge_lanes()
        if getattr(self, "_ports_migrated", False) or getattr(self, "_ui_migrated", False):
            self._persist()

    def _add_node(self):
        kind_u = (self.cbo_kind.currentText() or "CARGA").upper()
        name, ok = QInputDialog.getText(self, "Nuevo nodo", "Nombre/Tag del nodo:")
        if not ok:
            return
        name = _norm_txt(name) or kind_u

        dc_system = ""
        meta: Dict = {}

        if kind_u in ("TGCC", "TDCC"):
            dc_system = (self.cbo_dc.currentText() or "B1").strip() or "B1"
        elif kind_u == "CARGADOR":
            dc_system = (self.cbo_dc.currentText() or "B1").strip() or "B1"
            meta = {"needs_ac": True, "needs_dc": True}
        elif kind_u == "CARGA":
            sel, ok = QInputDialog.getItem(
                self, "Tipo de alimentación", "Esta carga requiere alimentación:", ["CA", "CC", "CA+CC"], 0, False
            )
            if not ok:
                return
            sel_u = (sel or "CA").upper()
            meta = {"needs_ac": ("CA" in sel_u), "needs_dc": ("CC" in sel_u)}
            if meta["needs_dc"]:
                dc_system = (self.cbo_dc.currentText() or "B1").strip() or "B1"

        node = TopoNode(
            id=_new_id(kind_u),
            kind=kind_u,
            name=name,
            pos=(60.0 + 40.0 * len(self._node_items), 60.0 + 20.0 * len(self._node_items)),
            dc_system=dc_system or "B1",
            p_w=0.0,
            meta=meta,
        )
        self._add_node_item(node)
        # Persist + issues (pipeline)
        self._controller.after_topology_mutation(
            rebuild_edges=False,
            recompute_load_table=False,
            refresh_feeders=False,
            refresh_issues=True,
        )


    def _add_calculated_charger(self):
        p = getattr(self.data_model, "proyecto", {}) or {}
        i_com = p.get("charger_a_comercial", "—")
        p_ca_w = to_float(p.get("charger_p_ca_w", 0.0), 0.0)
        if i_com in (None, "", "—") and p_ca_w <= 0:
            QMessageBox.information(
                self, "Cargador",
                "No hay cargador calculado/seleccionado aún en la pestaña 'Banco y cargador'."
            )
            return

        dc_system = (self.cbo_dc.currentText() or "B1").strip() or "B1"
        name = f"CARGADOR {i_com}" if i_com not in (None, "", "—") else "CARGADOR"

        node = TopoNode(
            id=_new_id("CARGADOR"),
            kind="CARGADOR",
            name=name,
            pos=(120.0 + 40.0 * len(self._node_items), 140.0 + 20.0 * len(self._node_items)),
            dc_system=dc_system,
            p_w=p_ca_w if p_ca_w > 0 else 0.0,
            meta={"charger_a_comercial": i_com, "source": "bank_charger", "needs_ac": True, "needs_dc": True},
        )
        self._add_node_item(node)
        self._persist()

    def _toggle_connect(self, checked: bool):
        self._connect_mode = bool(checked)
        self._connect_first = None
        if checked:
            QMessageBox.information(self, "Conectar", "Modo conectar activo. Selecciona el nodo origen y luego el nodo destino.")

    @safe_slot
    def _on_circuit_changed(self, *args, **kwargs):
        return

    @safe_slot
    def _on_dc_changed(self, *args, **kwargs):
        return

    def _add_dc_system(self, *args, **kwargs):
        return

    @safe_slot
    def _on_selection_changed(self):
        if not self._connect_mode:
            return

        selected_nodes = [it for it in self.scene.selectedItems() if isinstance(it, TopoNodeItem)]
        if not selected_nodes:
            return

        last = selected_nodes[-1]
        if self._connect_first is None:
            self._connect_first = last.node.id
            return

        src = self._connect_first
        dst = last.node.id
        if src == dst:
            return

        # conexión verificada (no dup, no ciclo)
        layer = self._selected_issue_layer()
        circuit = layer["circuit"]
        dc = layer["dc"]

        if self._connect_nodes_checked(circuit, dc, src, dst):
            self._connect_first = None

        # mantener modo conectar activo

    @safe_slot
    def _on_node_moved(self, _nid: str, _pos):
        self._persist()
        self._rebuild_edges_only()

    # ---------------- capa/issue helpers ----------------
    @safe_slot
    def _on_port_clicked(self, node_id: str, port_id: str, side: str):
        side = (side or "").upper()

        # 1) Primer click: guardar origen
        if self._pending_port is None:
            self._pending_port = (node_id, port_id, side)
            return

        # 2) Segundo click: conectar
        src_node, src_port, src_side = self._pending_port
        dst_node, dst_port, dst_side = node_id, port_id, side
        self._pending_port = None

        if src_node == dst_node and src_port == dst_port:
            return

        # Regla: OUT -> IN
        if src_side == dst_side:
            QMessageBox.warning(self, "Conexión", "Debes conectar OUT -> IN.")
            return

        # Asegurar que src sea OUT
        if src_side != "OUT" and dst_side == "OUT":
            src_node, src_port, src_side, dst_node, dst_port, dst_side = dst_node, dst_port, dst_side, src_node, src_port, src_side

        if src_side != "OUT" or dst_side != "IN":
            QMessageBox.warning(self, "Conexión", "Conexión inválida. Usa OUT -> IN.")
            return

        layer = self._selected_issue_layer()
        circuit = (layer["circuit"] or "CA").upper()
        dc = (layer["dc"] or "B1").strip() or "B1"

        # Workspace (pestaña activa) usado para filtrar nodos/aristas por capa.
        # Coincide con node.meta["layer"].
        ws = getattr(self, "_workspace", None) or getattr(self, "_ws", None) or "CA_ES"

        # evitar ciclos/duplicados usando tu método existente
        # (pero ahora con puertos en meta)
        if self._would_create_cycle(circuit, dc, src_node, dst_node):
            QMessageBox.warning(self, "Conexión", "Esa conexión generaría un ciclo. Se canceló.")
            return

        # duplicado (mismo src/dst en capa)
        for it in self._edge_items.values():
            e = it.edge
            if e.src == src_node and e.dst == dst_node and (e.circuit or "CA").upper() == circuit:
                if circuit != "CC" or (e.dc_system or "B1") == dc:
                    return

        edge = TopoEdge(
            id=_new_id("E"),
            src=src_node,
            dst=dst_node,
            circuit=circuit,
            dc_system=(dc if circuit == "CC" else ""),
            meta={"src_port": src_port, "dst_port": dst_port, "layer": ws, "out_port_id": src_port},
        )
        self._assign_edge_lane(edge)
        self._add_edge_item(edge)
        self._persist()
        if self._auto_place_children:
            src_item = self._node_items.get(src_node)
            if src_item is not None:
                auto_place_children(src_item, [edge], self._node_items, only_unpinned=True)
        self._rebuild_all_edges()

    def _refresh_issues_layer_combo(self, *args, **kwargs):
        return

    def _selected_issue_layer(self) -> dict:
        ws = getattr(self, "_workspace", "CA_ES")
        if ws == "CA_NOES":
            return {"circuit": "CA", "dc": ""}
        if ws == "CC_B1":
            return {"circuit": "CC", "dc": "B1"}
        if ws == "CC_B2":
            return {"circuit": "CC", "dc": "B2"}
        return {"circuit": "CA", "dc": ""}
    def _edges_in_layer(self, edges: List[TopoEdge], circuit: str, dc: str) -> List[TopoEdge]:
        circuit_u = (circuit or "CA").upper()
        out: List[TopoEdge] = []
        for e in edges:
            ec = (e.circuit or "CA").upper()
            if ec != circuit_u:
                continue
            if circuit_u == "CC" and (e.dc_system or "B1") != (dc or "B1"):
                continue
            out.append(e)
        return out

    
    # ---------------- cuadro de cargas (ventana flotante) ----------------
    def _compute_load_table_rows(self):
        """Suma P de cargas aguas abajo para cada tablero."""
        nodes = [it.node for it in self._node_items.values()]
        edges = [it.edge for it in self._edge_items.values()]
        by_id = {n.id: n for n in nodes}
        outs: Dict[str, List[TopoEdge]] = {}
        for e in edges:
            outs.setdefault(e.src, []).append(e)

        def downstream_sum(start_id: str, circuit: str, dc_system: str) -> float:
            seen = set()
            total = 0.0

            def dfs(nid: str):
                nonlocal total
                if nid in seen:
                    return
                seen.add(nid)
                for ee in outs.get(nid, []):
                    if (ee.circuit or "CA").upper() != circuit:
                        continue
                    if circuit == "CC" and (ee.dc_system or "B1") != dc_system:
                        continue
                    dn = by_id.get(ee.dst)
                    if dn is None:
                        continue
                    if dn.kind.upper() in ("CARGA", "CARGADOR"):
                        total += float(dn.p_w or 0.0)
                    dfs(dn.id)

            dfs(start_id)
            return total

        rows = []
        dc_systems = list(self._topo_store().get("dc_systems", ["B1"])) or ["B1"]
        for n in nodes:
            if n.kind.upper() not in ("TGCA", "TDCA", "TDAyF", "TGCC", "TDCC"):
                continue

            pca = downstream_sum(n.id, "CA", "")
            if pca > 0:
                rows.append((n.name, n.kind, "CA", "—", pca))

            for dc in dc_systems:
                pcc = downstream_sum(n.id, "CC", dc)
                if pcc > 0:
                    rows.append((n.name, n.kind, "CC", dc, pcc))

        return rows

    def _show_load_table_dialog(self):
        if not hasattr(self, "_load_table_dlg") or self._load_table_dlg is None:
            self._load_table_dlg = LoadTableDialog(parent=self)
        self._load_table_dlg.set_rows(self._compute_load_table_rows())
        self._load_table_dlg.show()
        self._load_table_dlg.raise_()
        self._load_table_dlg.activateWindow()

    def _validate_rules_layered(self, nodes: List[TopoNode], edges: List[TopoEdge], circuit: str, dc: str) -> List[Dict]:
        issues: List[Dict] = []
        by_id = {n.id: n for n in nodes}
        ledges = self._edges_in_layer(edges, circuit, dc)

        seen_pairs = set()
        for e in ledges:
            if e.src == e.dst:
                issues.append({"level": "error", "code": "EDGE_SELF_LOOP", "msg": f"Self-loop: {e.src}", "node_id": e.src, "edge_id": e.id})
            pair = (e.src, e.dst, (e.circuit or "CA").upper(), (e.dc_system or ""))
            if pair in seen_pairs:
                issues.append({"level": "warn", "code": "EDGE_DUPLICATE", "msg": f"Arista duplicada: {e.src} -> {e.dst}", "edge_id": e.id})
            else:
                seen_pairs.add(pair)

        # ciclo: DFS
        outs: Dict[str, List[str]] = {}
        for e in ledges:
            outs.setdefault(e.src, []).append(e.dst)

        temp: set = set()
        perm: set = set()
        cycle_nodes: set = set()

        def dfs(u: str):
            if u in perm:
                return False
            if u in temp:
                cycle_nodes.add(u)
                return True
            temp.add(u)
            for v in outs.get(u, []):
                if dfs(v):
                    cycle_nodes.add(u)
                    return True
            temp.remove(u)
            perm.add(u)
            return False

        for nid in list(outs.keys()):
            dfs(nid)

        for nid in cycle_nodes:
            nm = by_id.get(nid).name if by_id.get(nid) else nid
            issues.append({"level": "error", "code": "GRAPH_CYCLE", "msg": f"Se detectó ciclo en la capa (nodo: {nm}).", "node_id": nid})

        # huérfanos: cargas/cargadores sin incoming en esta capa
        incoming = {n.id: 0 for n in nodes}
        for e in ledges:
            incoming[e.dst] = incoming.get(e.dst, 0) + 1

        for n in nodes:
            if (n.kind or "").upper() not in ("CARGA", "CARGADOR"):
                continue

            # Si el usuario eliminó todos los puertos de entrada del nodo,
            # entonces no es conectable por diseño → no lo reportamos como huérfano.
            ports = (n.meta or {}).get("ports", []) or []
            has_in = any((p.get("io") or "").upper() == "IN" for p in ports)
            if not has_in:
                continue
            if circuit_u := (circuit or "CA").upper() == "CC":
                if (n.meta or {}).get("circuit") == "CC":
                    # ok
                    pass
            if (circuit or "CA").upper() == "CC":
                # si el nodo declara dc_system en meta, exigir match
                n_dc = (n.meta or {}).get("dc_system") or ""
                if n_dc and n_dc != (dc or "B1"):
                    continue
            if incoming.get(n.id, 0) == 0:
                issues.append({"level": "warn", "code": "NODE_ORPHAN", "msg": f"Carga huérfana: {n.name}", "node_id": n.id})

        for n in nodes:
            if not (n.meta or {}).get("root_board"):
                continue
            if incoming.get(n.id, 0) > 0:
                issues.append({
                    "level": "error",
                    "code": "ROOT_BOARD_HAS_INCOMING_EDGE",
                    "msg": f"Tablero raíz con entrada: {n.name}",
                    "node_id": n.id,
                })

        # Fuentes: no deben tener aristas entrantes y no deben duplicarse por capa
        source_ids_by_key: Dict[str, List[str]] = {}
        for n in nodes:
            if (n.kind or "").upper() != "FUENTE":
                continue
            if incoming.get(n.id, 0) > 0:
                issues.append({
                    "level": "error",
                    "code": "SOURCE_HAS_INCOMING_EDGE",
                    "msg": f"Fuente con entrada: {n.name}",
                    "node_id": n.id,
                })
            key = (n.meta or {}).get("source_key") or (n.meta or {}).get("gabinete_id") or n.name
            source_ids_by_key.setdefault(str(key), []).append(n.id)

        for key, ids in source_ids_by_key.items():
            if len(ids) > 1:
                issues.append({
                    "level": "warn",
                    "code": "SOURCE_DUPLICATE_IN_LAYER",
                    "msg": f"Fuente duplicada en la capa (key={key}).",
                    "node_id": ids[0],
                })

        # ------------------------------------------------------
        # Regla crítica: discrepancia entre arquitectura dibujada
        # y selección vigente en "Alimentación tableros"
        # ------------------------------------------------------
        def _find_comp_data(gab_id: str, comp_id: str) -> dict:
            for g in getattr(self.data_model, "gabinetes", []) or []:
                if g.get("id") == gab_id:
                    for c in g.get("components", []) or []:
                        if c.get("id") == comp_id:
                            return c.get("data", {}) or {}
            return {}

        flag_by_req = {
            "CC B1": "feed_cc_b1",
            "CC B2": "feed_cc_b2",
            "CA ESENCIAL": "feed_ca_esencial",
            "CA NO ESENCIAL": "feed_ca_no_esencial",
        }

        expected_req = None
        if circuit == "CC":
            expected_req = f"CC {dc}"
        else:
            expected_req = "CA ESENCIAL" if dc == "ESENCIAL" else "CA NO ESENCIAL"

        for n in nodes:
            if (n.kind or "").upper() not in ("CARGA", "CARGADOR"):
                continue
            if (n.meta or {}).get("source") != "board_feed":
                continue

            req = (n.meta or {}).get("feed_req", "")
            if req != expected_req:
                continue  # se valida solo en su propia capa

            gab_id = (n.meta or {}).get("gabinete_id", "")
            comp_id = (n.meta or {}).get("component_id", "")
            if not gab_id or not comp_id:
                issues.append({
                    "level": "error",
                    "code": "FEED_MISMATCH",
                    "msg": f"[{expected_req}] Nodo '{n.tag}' no tiene referencia a gabinete/componente (meta incompleta).",
                })
                continue

            data = _find_comp_data(gab_id, comp_id)
            if not data:
                issues.append({
                    "level": "error",
                    "code": "FEED_MISMATCH",
                    "msg": f"[{expected_req}] Nodo '{n.tag}' refiere a un componente eliminado o no encontrado en el proyecto.",
                })
                continue

            flag_key = flag_by_req.get(expected_req)
            if flag_key and not bool(data.get(flag_key, False)):
                issues.append({
                    "level": "error",
                    "code": "FEED_MISMATCH",
                    "msg": (
                        f"[{expected_req}] Nodo '{n.tag}' está dibujado en Arquitectura SS/AA, "
                        f"pero en 'Alimentación tableros' esta alimentación está desmarcada "
                        f"({flag_key}=False)."
                    ),
                })

        return issues

    def _validate_feed_mismatches_global(self, nodes):
        """Validación global (crítica): nodos dibujados cuya alimentación fue desmarcada en 'Alimentación tableros'.

        Se muestra SIEMPRE en el panel de Validaciones, independiente de la capa actualmente seleccionada,
        para evitar que el usuario 'pierda' el error si la pestaña/capa desaparece.
        """
        issues = []

        # Mapeo: feed_req (meta del nodo) -> flag guardado en data del componente
        req_to_flag = {
            "CA_ES": "feed_ca_esencial",
            "CA_NE": "feed_ca_no_esencial",
            "CC_B1": "feed_cc_b1",
            "CC_B2": "feed_cc_b2",
        }

        def _find_comp_data(gab_id: str, comp_id: str) -> dict:
            for g in getattr(self.data_model, "gabinetes", []) or []:
                if g.get("id") == gab_id:
                    for c in g.get("components", []) or []:
                        if c.get("id") == comp_id:
                            return c.get("data", {}) or {}
            return {}

        for n in nodes or []:
            req = (n.meta or {}).get("feed_req", "")
            if not req:
                continue

            flag_key = req_to_flag.get(req)
            if not flag_key:
                continue

            gab_id = (n.meta or {}).get("gabinete_id", "")
            comp_id = (n.meta or {}).get("component_id", "")
            if not gab_id or not comp_id:
                # Meta incompleta: también es crítico, porque impide validar correctamente
                issues.append({
                    "level": "error",
                    "code": "FEED_MISMATCH",
                    "msg": f"[{req}] Nodo '{getattr(n, 'tag', '') or getattr(n, 'name', '')}' no tiene referencia a gabinete/componente (meta incompleta).",
                })
                continue

            data = _find_comp_data(gab_id, comp_id)

            # Respeta el valor guardado: solo validar si la clave existe.
            if flag_key in data and bool(data.get(flag_key)) is False:
                issues.append({
                    "level": "error",
                    "code": "FEED_MISMATCH",
                    "msg": (
                        f"[{req}] Nodo '{getattr(n, 'tag', '')}' está dibujado en Arquitectura SS/AA, "
                        f"pero en 'Alimentación tableros' esta alimentación está desmarcada ({flag_key}=False)."
                    ),
                })

        return issues


    def _validate_cross_global(self, nodes):
        """Validaciones cruzadas críticas entre:
        - Arquitectura SS/AA (nodos dibujados, feeder_key)
        - Alimentación Tableros (selección vigente)
        - Consumos (potencias/tipo vs flags de alimentación)

        Objetivo: evitar inconsistencias silenciosas cuando el usuario cambia
        selecciones en 'Alimentación Tableros' o edita consumos.
        """
        issues = []

        # --------------------------------------------------
        # A) Arquitectura vs Alimentación Tableros (por feeder_key)
        # --------------------------------------------------
        # Construir conjunto de claves válidas actualmente seleccionadas
        current_keys = set()
        try:
            for req in ("CA_ES", "CA_NOES", "CC_B1", "CC_B2"):
                for row in self._iter_feed_rows() or []:
                    ok = False
                    if req == "CA_ES":
                        ok = bool(row.get("ca_es"))
                    elif req == "CA_NOES":
                        ok = bool(row.get("ca_noes"))
                    elif req == "CC_B1":
                        ok = bool(row.get("cc_b1"))
                    elif req == "CC_B2":
                        ok = bool(row.get("cc_b2"))

                    if not ok:
                        continue

                    gid_for_key = row.get("gid") or row.get("gi")
                    key = f"{row.get('scope')}:{gid_for_key}:{row.get('ci')}:{req}"
                    current_keys.add(key)
        except Exception:
            # Si falla la lectura de filas (no debería), no rompemos las validaciones.
            current_keys = set()

        node_keys = set()
        for n in nodes or []:
            if (n.meta or {}).get("source") != "board_feed":
                continue
            fk = (n.meta or {}).get("feeder_key")
            if not fk:
                continue
            node_keys.add(fk)
            if current_keys and fk not in current_keys:
                issues.append({
                    "level": "error",
                    "code": "ARCH_FEED_REMOVED",
                    "msg": (
                        f"Nodo '{getattr(n, 'tag', '') or getattr(n, 'name', '')}' sigue dibujado, "
                        f"pero su alimentación ya no está seleccionada en 'Alimentación Tableros' (key={fk})."
                    ),
                    "node_id": getattr(n, 'id', None),
                })

        # Alimentaciones seleccionadas pero no usadas en arquitectura
        try:
            topo = self._topo_store()
            used = set(topo.get("used_feeders", []) or [])
        except Exception:
            used = set()

        unused = [fk for fk in sorted(current_keys) if fk not in used and fk not in node_keys]
        if unused:
            preview = ", ".join(unused[:10])
            more = "" if len(unused) <= 10 else f" (+{len(unused) - 10} más)"
            issues.append({
                "level": "info",
                "code": "FEED_SELECTED_NOT_USED",
                "msg": (
                    "Hay alimentaciones seleccionadas en 'Alimentación Tableros' "
                    "que aún no se han dibujado en 'Arquitectura SS/AA'. "
                    f"({len(unused)}): {preview}{more}"
                ),
            })

        # --------------------------------------------------
        # A2) Fuentes de energía (Instalaciones) vs Arquitectura
        # --------------------------------------------------
        sources_defined: set[str] = set()
        for g in getattr(self.data_model, "gabinetes", []) or []:
            if bool(g.get("is_energy_source", False)):
                gid = str(g.get("id") or "").strip()
                gtag = str(g.get("tag") or "").strip()
                if gid:
                    sources_defined.add(gid)
                if gtag:
                    sources_defined.add(gtag)

        source_nodes = [n for n in (nodes or []) if (n.kind or "").upper() == "FUENTE"]
        for n in source_nodes:
            gid = (n.meta or {}).get("gabinete_id") or ""
            if gid and gid not in sources_defined:
                issues.append({
                    "level": "error",
                    "code": "SOURCE_REMOVED",
                    "msg": (
                        f"Fuente '{getattr(n, 'tag', '') or getattr(n, 'name', '')}' "
                        "refiere a un gabinete que ya no es fuente de energía o no existe."
                    ),
                    "node_id": getattr(n, "id", None),
                })

        if sources_defined and not source_nodes:
            issues.append({
                "level": "warn",
                "code": "SOURCE_SELECTED_NOT_USED",
                "msg": "Hay fuentes de energía definidas en Instalaciones, pero ninguna fue dibujada en Arquitectura SS/AA.",
            })

        # --------------------------------------------------
        # B) Alimentación Tableros vs Consumos (flags vs tipo/potencia)
        # --------------------------------------------------
        def _gab_name(g: dict) -> str:
            return (g.get("tag") or g.get("codigo") or g.get("nombre") or "").strip()

        def _comp_name(c: dict) -> str:
            return (c.get("name") or c.get("base") or "Consumo").strip()

        def _needs_power(tipo: str) -> bool:
            return True  # por ahora siempre exigimos potencia para consumos relevantes

        for g in getattr(self.data_model, "gabinetes", []) or []:
            g_label = _gab_name(g)
            for c in (g.get("components") or []):
                data = (c.get("data") or {})

                # flags de alimentación marcados a nivel consumo
                ca_es = bool(data.get("feed_ca_esencial", False))
                ca_ne = bool(data.get("feed_ca_no_esencial", False))
                cc_b1 = bool(data.get("feed_cc_b1", False))
                cc_b2 = bool(data.get("feed_cc_b2", False))
                any_feed = ca_es or ca_ne or cc_b1 or cc_b2
                if not any_feed:
                    continue

                tipo = str(data.get("tipo_consumo", "") or "")
                usar_va = bool(data.get("usar_va", False))
                pw = str(data.get("potencia_w", "") or "").strip()
                pva = str(data.get("potencia_va", "") or "").strip()

                # (1) Inconsistencia tipo vs flags
                if tipo.startswith("C.C.") and (ca_es or ca_ne):
                    issues.append({
                        "level": "error",
                        "code": "TYPE_MISMATCH",
                        "msg": (
                            f"[{g_label}] '{_comp_name(c)}' es C.C. pero tiene alimentación C.A. marcada (ES/NOES)."
                        ),
                    })
                if tipo.startswith("C.A.") and (cc_b1 or cc_b2):
                    issues.append({
                        "level": "error",
                        "code": "TYPE_MISMATCH",
                        "msg": (
                            f"[{g_label}] '{_comp_name(c)}' es C.A. pero tiene alimentación C.C. marcada (B1/B2)."
                        ),
                    })

                # (2) Potencia faltante
                if _needs_power(tipo):
                    missing = False
                    if tipo.startswith("C.C."):
                        missing = (pw == "")
                    else:
                        # C.A.
                        if usar_va:
                            missing = (pva == "")
                        else:
                            missing = (pw == "")
                    if missing:
                        issues.append({
                            "level": "warn",
                            "code": "MISSING_POWER",
                            "msg": (
                                f"[{g_label}] '{_comp_name(c)}' tiene alimentación marcada pero potencia no definida "
                                f"({'VA' if usar_va else 'W'})."
                            ),
                        })

        return issues

    @safe_slot
    def _refresh_issues_panel(self):
        return self._controller.refresh_issues_panel()

    def _suggest_feeder_for_node(self, target_id: str, circuit: str, dc: str):
        if target_id not in self._node_items:
            return None
        tgt_pos = self._node_items[target_id].pos()

        candidates = []
        for nid, item in self._node_items.items():
            if nid == target_id:
                continue
            k = (item.node.kind or "").upper()
            if k in ("CARGA", "CARGADOR"):
                continue
            if circuit.upper() == "CC":
                if (item.node.dc_system or "B1") != (dc or "B1"):
                    continue
            candidates.append(nid)

        if not candidates:
            return None

        def dist2(nid):
            p = self._node_items[nid].pos()
            dx = float(p.x() - tgt_pos.x())
            dy = float(p.y() - tgt_pos.y())
            return dx * dx + dy * dy

        candidates.sort(key=dist2)
        return candidates[0]

    def _would_create_cycle(self, circuit: str, dc: str, src: str, dst: str) -> bool:
        edges = [it.edge for it in self._edge_items.values()]
        ledges = self._edges_in_layer(edges, circuit, dc)
        outs: Dict[str, List[str]] = {}
        for e in ledges:
            outs.setdefault(e.src, []).append(e.dst)

        seen = set()
        stack = [dst]
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            for v in outs.get(u, []):
                if v == src:
                    return True
                stack.append(v)
        return False

    def _connect_nodes_checked(self, circuit: str, dc: str, src: str, dst: str) -> bool:
        return connect_nodes_checked(self, circuit, dc, src, dst)

    @safe_slot
    def _auto_connect_orphans_interactive(self):
        return auto_connect_orphans_interactive(self)

    @safe_slot
    def _connect_from_context(self, dst_node_id: str):
        return connect_from_context(self, dst_node_id)

    def _validate(self):
        nodes = [it.node for it in self._node_items.values()]
        edges = [it.edge for it in self._edge_items.values()]
        problems = self._validate_rules(nodes, edges)
        if problems:
            QMessageBox.warning(self, "Validación", "\n".join(problems[:25]))
        else:
            QMessageBox.information(self, "Validación", "OK: no se detectaron problemas básicos.")

    def _validate_rules(self, nodes: List[TopoNode], edges: List[TopoEdge]) -> List[str]:
        probs: List[str] = []
        by_id = {n.id: n for n in nodes}

        for e in edges:
            if e.src not in by_id:
                probs.append(f"Arista {e.id}: origen no existe ({e.src}).")
            if e.dst not in by_id:
                probs.append(f"Arista {e.id}: destino no existe ({e.dst}).")

        # CC: sistema DC debe coincidir con nodos involucrados cuando corresponda
        for e in edges:
            if (e.circuit or "CA").upper() != "CC":
                continue
            s = by_id.get(e.src)
            d = by_id.get(e.dst)
            if s and s.kind.upper() in ("TGCC", "TDCC", "CARGADOR"):
                if (s.dc_system or "B1") != (e.dc_system or "B1"):
                    probs.append(f"Arista {e.id}: CC sistema DC no coincide con origen ({s.name}).")
            if d and d.kind.upper() in ("TGCC", "TDCC", "CARGADOR"):
                if (d.dc_system or "B1") != (e.dc_system or "B1"):
                    probs.append(f"Arista {e.id}: CC sistema DC no coincide con destino ({d.name}).")

        return probs
