# -*- coding: utf-8 -*-
"""QGraphicsItem implementations for SSAA Designer.

Extracted from ssaa_designer_screen.py to keep the screen module focused on
composition/wiring.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Tuple

from domain.ssaa_topology import TopoNode, TopoEdge

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush, QFont, QPainterPath, QFontMetrics
from PyQt5.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsTextItem,
    QGraphicsRectItem,
    QMessageBox,
    QInputDialog,
)

from .constants import GRID
from .layout_constants import (
    CARD_WIDTH,
    SOURCE_CARD_WIDTH,
    BOARD_MIN_WIDTH,
    EDGE_CLEARANCE,
    MIN_LANE_GAP,
)
from .port_layout import compute_port_positions, compute_node_width


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class TopoNodeItem(QGraphicsItem):
    """Nodo arrastrable con snap a grilla."""

    def __init__(self, node: TopoNode, on_moved=None, on_connect_from=None, on_port_clicked=None, on_port_added=None):
        super().__init__()
        self.node = node
        self._on_moved = on_moved
        self._on_connect_from = on_connect_from
        self._on_port_clicked = on_port_clicked
        self._on_port_added = on_port_added

        self._port_items = {}

        self._font_title = QFont("Segoe UI", 9)
        self._font_title.setBold(True)
        self._font_body = QFont("Segoe UI", 8)

        self._ui_changed = self._ensure_ui_meta()
        self._ensure_default_ports()
        self._ports_changed = self._ensure_required_ports()
        self._rebuild_ports()

        self._pending_port = None  # (node_id, port_id, side)

        self.setPos(QPointF(node.pos[0], node.pos[1]))
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )

    def _default_ui_size(self) -> Tuple[float, float]:
        kind = (self.node.kind or "").upper()
        fixed_w = {
            "FUENTE": SOURCE_CARD_WIDTH,
            "CARGA": CARD_WIDTH,
            "CARGADOR": 280.0,
            "TGCA": BOARD_MIN_WIDTH,
            "TDCA": BOARD_MIN_WIDTH,
            "TGCC": BOARD_MIN_WIDTH,
            "TDCC": BOARD_MIN_WIDTH,
            "TDAF": BOARD_MIN_WIDTH,
            "TDAyF": BOARD_MIN_WIDTH,
        }
        fixed_h = {
            "FUENTE": 90.0,
            "CARGA": 110.0,
            "CARGADOR": 100.0,
            "TGCA": 110.0,
            "TDCA": 110.0,
            "TGCC": 110.0,
            "TDCC": 110.0,
            "TDAF": 110.0,
            "TDAyF": 110.0,
        }
        return fixed_w.get(kind, 260.0), fixed_h.get(kind, 100.0)

    def _ensure_ui_meta(self) -> bool:
        meta = self.node.meta or {}
        ui = meta.get("ui")
        changed = False
        if not isinstance(ui, dict):
            ui = {}
            changed = True

        def_w, def_h = self._default_ui_size()
        w = float(ui.get("w") or def_w)
        h = float(ui.get("h") or def_h)
        kind = (self.node.kind or "").upper()
        if kind == "CARGA":
            desc = (meta.get("desc") or "").strip()
            max_w = w - 16.0
            desc_lines, _ = self._wrap_text(f"DESCRIPCIÓN: {desc}", self._font_body, max_w, 3)
            h = max(h, 42.0 + 14.0 * (len(desc_lines) + 2))
        ui.setdefault("expanded", True)
        if ui.get("w") != int(w):
            ui["w"] = int(w)
            changed = True
        if ui.get("h") != int(h):
            ui["h"] = int(h)
            changed = True
        meta["ui"] = ui
        self.node.meta = meta
        self.node.size = (float(ui["w"]), float(ui["h"]))
        return changed

    def _wrap_text(self, text: str, font: QFont, max_width: float, max_lines: int) -> Tuple[List[str], bool]:
        txt = (text or "").strip()
        if not txt:
            return [""], False
        fm = QFontMetrics(font)
        words = txt.split()
        lines: List[str] = []
        cur = ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if fm.horizontalAdvance(trial) <= max_width or not cur:
                cur = trial
                continue
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
        if len(lines) < max_lines and cur:
            lines.append(cur)
        truncated = False
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True
        if lines and fm.horizontalAdvance(lines[-1]) > max_width:
            lines[-1] = fm.elidedText(lines[-1], Qt.ElideRight, int(max_width))
            truncated = True
        if len(lines) == max_lines and " ".join(words) not in " ".join(lines):
            truncated = True
            lines[-1] = fm.elidedText(lines[-1], Qt.ElideRight, int(max_width))
        return lines, truncated


    def _ensure_default_ports(self):
        meta = self.node.meta or {}
        ports = meta.get("ports")
        if not isinstance(ports, list) or not ports:
            kind = (self.node.kind or "").upper()
            if kind == "FUENTE":
                ports = [
                    {"id": _new_id("p"), "name": "OUT", "io": "OUT", "side": "bottom", "x": 0.5},
                ]
            else:
                ports = [
                    {"id": _new_id("p"), "name": "IN", "io": "IN", "side": "top", "x": 0.5},
                    {"id": _new_id("p"), "name": "OUT", "io": "OUT", "side": "bottom", "x": 0.5},
                ]
            meta["ports"] = ports
            self.node.meta = meta

    def _ensure_required_ports(self) -> bool:
        meta = self.node.meta or {}
        ports = meta.get("ports", []) or []
        kind = (self.node.kind or "").upper()
        changed = False

        if kind == "FUENTE":
            before = list(ports)
            ports = [p for p in ports if (p.get("io") or "").upper() != "IN"]
            if before != ports:
                changed = True
            if not ports:
                ports = [{"id": _new_id("p"), "name": "OUT", "io": "OUT", "side": "bottom", "x": 0.5}]
                changed = True
        elif kind.startswith(("TG", "TD", "TDA")):
            has_in = any((p.get("io") or "").upper() == "IN" for p in ports)
            if not has_in:
                ports.insert(0, {"id": _new_id("p"), "name": "IN", "io": "IN", "side": "top", "x": 0.5})
                changed = True

        meta["ports"] = ports
        self.node.meta = meta
        return changed

    def _rebuild_ports(self):
        # remove old
        for pit in list(self._port_items.values()):
            pit.setParentItem(None)
            if pit.scene():
                pit.scene().removeItem(pit)
        self._port_items = {}

        meta = self.node.meta or {}
        ports = meta.get("ports", []) or []
        for pd in ports:
            pid = str(pd.get("id") or "")
            if not pid:
                continue
            pit = PortItem(node_item=self, port_id=pid, name=str(pd.get("name") or ""), io=str(pd.get("io") or ""), side=str(pd.get("side") or "top"), on_clicked=self._on_port_clicked)
            pit.setParentItem(self)
            self._port_items[pid] = pit
        self._layout_ports(force=False)


    def _layout_ports(self, force: bool = False):
        """Distribuye puertos como en el esquema de referencia.

        Variables:
        - Z: margen fijo desde el borde izquierdo/derecho.
        - X: separación entre puertos, calculada para ocupar el ancho disponible.

        Para n==1: puerto centrado.
        Para n>=2: puertos en [Z .. (w-Z)] con separación uniforme (X).
        """
        w, h = self.node.size
        meta = self.node.meta or {}
        ports = meta.get("ports", []) or []

        # recalcular posiciones solo cuando falta x o es inválido (o force)
        for side in ("top", "bottom"):
            group = []
            for pd in ports:
                pd_side = str(pd.get("side") or "").lower()
                if not pd_side:
                    io = str(pd.get("io") or "").upper()
                    pd_side = "top" if io == "IN" else "bottom"
                    pd["side"] = pd_side
                if pd_side == side:
                    group.append(pd)
            need = force or any(pd.get("x") is None or not isinstance(pd.get("x"), (int, float)) for pd in group)
            if not need:
                continue
            pts = compute_port_positions(self.boundingRect(), len(group), side)
            for pd, pt in zip(group, pts):
                pd["x"] = (pt.x() / w) if w else 0.5

        # aplicar posición a items
        for pid, pit in self._port_items.items():
            pd = None
            for d in ports:
                if str(d.get("id")) == pid:
                    pd = d
                    break
            if not pd:
                continue
            side = str(pd.get("side") or "top").lower()
            x_rel = float(pd.get("x", 0.5))
            x_rel = max(0.0, min(1.0, x_rel))
            x = x_rel * w
            y = 0.0 if side == "top" else h
            pit.setPos(QPointF(x, y))

    def port_scene_pos(self, port_id: str) -> QPointF:
        pit = self._port_items.get(port_id)
        if pit is None:
            # fallback: center
            r = self.boundingRect()
            return self.mapToScene(r.center())
        return pit.mapToScene(pit.boundingRect().center())


    def add_port(self, io: str):
        """Agrega un puerto IN (arriba) u OUT (abajo)."""
        io_u = (io or "OUT").upper()
        side = "top" if io_u == "IN" else "bottom"

        meta = self.node.meta or {}
        ports = meta.get("ports", []) or []

        pid = _new_id("p")
        # nombre sugerido
        same = [p for p in ports if (p.get("io") or "").upper() == io_u]
        name = io_u if not same else f"{io_u}{len(same)+1}"

        ports.append({"id": pid, "name": name, "io": io_u, "side": side, "x": None})
        meta["ports"] = ports
        ui = meta.get("ui") if isinstance(meta.get("ui"), dict) else {}
        if io_u == "IN":
            ui["desired_in_ports"] = int(ui.get("desired_in_ports") or 1) + 1
        else:
            ui["desired_out_ports"] = int(ui.get("desired_out_ports") or 1) + 1
        meta["ui"] = ui
        self.node.meta = meta

        self._autoresize_for_ports()
        self._rebuild_ports()
        self._layout_ports(force=True)

        if self._on_port_added:
            self._on_port_added(self.node.id)


    def remove_port(self, port_id: str):
        meta = self.node.meta or {}
        ports = meta.get("ports", []) or []
        port_id = str(port_id or "")
        if not port_id:
            return

        remaining = [p for p in ports if str(p.get("id")) != port_id]
        if len(remaining) == len(ports):
            return

        # Permitir que el usuario deje el nodo sin IN (o sin OUT) si así lo desea.
        # Solo evitamos dejarlo sin puertos en absoluto.
        if len(remaining) == 0:
            return

        meta["ports"] = remaining
        self.node.meta = meta
        self._autoresize_for_ports()
        self._rebuild_ports()
        if self._on_port_added:
            self._on_port_added(self.node.id)

    def _autoresize_for_ports(self):
        kind = (self.node.kind or "").upper()
        if kind.startswith(("TG", "TD", "TDA")):
            meta = self.node.meta or {}
            ports = meta.get("ports", []) or []
            n_in = sum(1 for p in ports if (p.get("io") or "").upper() == "IN")
            n_out = sum(1 for p in ports if (p.get("io") or "").upper() == "OUT")
            new_w = compute_node_width(kind, n_in, n_out)
            old_w, old_h = self.node.size
            if abs(old_w - new_w) > 0.5:
                center_x = self.pos().x() + old_w / 2.0
                self.prepareGeometryChange()
                self.node.size = (float(new_w), float(old_h))
                meta_ui = meta.get("ui") if isinstance(meta.get("ui"), dict) else {}
                meta_ui["w"] = int(new_w)
                meta["ui"] = meta_ui
                self.node.meta = meta
                self.setPos(QPointF(center_x - new_w / 2.0, self.pos().y()))
        return

    def boundingRect(self) -> QRectF:
        w, h = self.node.size
        return QRectF(0, 0, w, h)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            x = round(value.x() / GRID) * GRID
            y = round(value.y() / GRID) * GRID
            return QPointF(x, y)

        if change == QGraphicsItem.ItemPositionHasChanged:
            p = self.pos()
            self.node.pos = (float(p.x()), float(p.y()))
            meta = self.node.meta or {}
            ui = meta.get("ui") if isinstance(meta.get("ui"), dict) else {}
            ui["manual_pos"] = True
            meta["ui"] = ui
            self.node.meta = meta
            if self._on_moved:
                self._on_moved(self.node.id, self.node.pos)

        return super().itemChange(change, value)



    def contextMenuEvent(self, event):
        try:
            from PyQt5.QtWidgets import QMenu

            menu = QMenu()
            act_in = menu.addAction("Agregar puerto IN (arriba)")
            act_out = menu.addAction("Agregar puerto OUT (abajo)")

            menu.addSeparator()

            # Submenu eliminar puerto
            sub_del = menu.addMenu("Eliminar puerto")
            ports = (self.node.meta or {}).get("ports", []) or []
            actions = []
            for pd in ports:
                pid = str(pd.get("id") or "")
                if not pid:
                    continue
                label = f"{pd.get('name','P')} ({(pd.get('io') or '').upper() or 'OUT'})"
                a = sub_del.addAction(label)
                a.setData(pid)
                actions.append(a)

            menu.addSeparator()
            act_conn = menu.addAction("Conectar desde… (modo antiguo)")

            chosen = menu.exec_(event.screenPos())
            if chosen == act_in:
                self.add_port("IN")
            elif chosen == act_out:
                self.add_port("OUT")
            elif chosen in actions:
                pid = chosen.data()
                if pid:
                    self.remove_port(str(pid))
            elif chosen == act_conn and self._on_connect_from:
                self._on_connect_from(self.node.id)
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    def paint(self, painter: QPainter, _opt, _w=None):
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.boundingRect()

        kind = (self.node.kind or "").upper()
        meta = self.node.meta or {}

        # ---- Fill por tipo ----
        fill = QColor(255, 255, 255)
        if kind in ("TGCA", "TDCA"):
            fill = QColor(235, 245, 255)
        elif kind in ("TGCC", "TDCC"):
            fill = QColor(240, 255, 240)
        elif kind == "TDAyF":
            fill = QColor(255, 248, 230)
        elif kind == "CARGADOR":
            fill = QColor(245, 240, 255)
        elif kind == "CARGA":
            fill = QColor(250, 250, 250)

        # ---- Borde + fondo primero ----
        pen = QPen(QColor(30, 64, 175), 3) if self.isSelected() else QPen(QColor(0, 0, 0), 1)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill))
        painter.drawRoundedRect(r, 8, 8)

        # ---- Texto ----
        painter.setPen(QColor(0, 0, 0))

        if kind == "CARGA":
            tag = (meta.get("tag") or self.node.name or "").strip()
            desc = (meta.get("desc") or "").strip()
            load = (meta.get("load") or "").strip() or "Alimentación General"

            max_w = r.width() - 16
            fm_title = QFontMetrics(self._font_title)
            fm_body = QFontMetrics(self._font_body)
            title = fm_title.elidedText(f"TAG: {tag}", Qt.ElideRight, int(max_w))

            painter.setFont(self._font_title)
            painter.drawText(QRectF(8, 6, max_w, 18),
                            Qt.AlignLeft | Qt.AlignVCenter,
                            title)

            painter.setFont(self._font_body)
            y = 28
            desc_lines, desc_trunc = self._wrap_text(f"DESCRIPCIÓN: {desc}", self._font_body, max_w, 3)
            for ln in desc_lines:
                painter.drawText(QRectF(8, y, max_w, 14),
                                Qt.AlignLeft | Qt.AlignVCenter,
                                ln)
                y += 14
            load_line = fm_body.elidedText(f"CARGA: {load}", Qt.ElideRight, int(max_w))
            painter.drawText(QRectF(8, y, max_w, 14),
                            Qt.AlignLeft | Qt.AlignVCenter,
                            load_line)

            if desc_trunc:
                self.setToolTip(f"{tag}\n{desc}\n{load}")
            else:
                self.setToolTip(f"{tag}\n{desc}\n{load}")
            return

        # Otros nodos: título + 2 líneas
        painter.setFont(self._font_title)
        max_w = r.width() - 16
        fm_title = QFontMetrics(self._font_title)
        title = f"{self.node.kind}: {self.node.name}" if self.node.name else f"{self.node.kind}"
        title = fm_title.elidedText(title, Qt.ElideRight, int(max_w))
        painter.drawText(QRectF(8, 6, max_w, 18),
                        Qt.AlignLeft | Qt.AlignVCenter,
                        title)

        painter.setFont(self._font_body)
        y = 28
        lines: List[str] = []
        if kind in ("TGCC", "TDCC", "CARGADOR") and self.node.dc_system:
            lines.append(f"Sistema DC: {self.node.dc_system}")
        if kind in ("CARGA", "CARGADOR") and (self.node.p_w or 0.0) > 0:
            lines.append(f"P: {self.node.p_w:.0f} W")

        fm_body = QFontMetrics(self._font_body)
        for ln in lines[:2]:
            txt = fm_body.elidedText(ln, Qt.ElideRight, int(max_w))
            painter.drawText(QRectF(8, y, max_w, 14),
                            Qt.AlignLeft | Qt.AlignVCenter,
                            txt)
            y += 14


class PortItem(QGraphicsItem):
    """Puerto de conexión (círculo) anclado al nodo."""

    R = 6.0

    def __init__(self, node_item: TopoNodeItem, port_id: str, name: str, io: str, side: str, on_clicked=None):
        super().__init__(node_item)
        self.node_item = node_item
        self.port_id = port_id
        self.name = name
        self.side = (side or "top").lower()
        self.io = (io or name or '').upper()
        self._on_clicked = on_clicked
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

    def boundingRect(self) -> QRectF:
        return QRectF(-self.R, -self.R, 2*self.R, 2*self.R)

    def paint(self, painter: QPainter, _opt, _w=None):
        painter.setRenderHint(QPainter.Antialiasing)
        is_hover = getattr(self, "_hover", False)
        pen = QPen(QColor(30, 64, 175), 2) if is_hover else QPen(QColor(0, 0, 0), 1)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(self.boundingRect())

    def hoverEnterEvent(self, event):
        self._hover = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hover = False
        self.update()
        super().hoverLeaveEvent(event)


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._on_clicked:
            io = self.io or ("IN" if self.side == "top" else "OUT")
            self._on_clicked(self.node_item.node.id, self.port_id, io)
            event.accept()
            return
        super().mousePressEvent(event)

class TopoEdgeItem(QGraphicsPathItem):
    def __init__(self, edge: TopoEdge, src_item: TopoNodeItem, dst_item: TopoNodeItem):
        super().__init__()
        self.edge = edge
        self.src_item = src_item
        self.dst_item = dst_item
        self.setFlag(QGraphicsPathItem.ItemIsSelectable, True)
        self.setZValue(-10)
        self._label_bg = QGraphicsRectItem(self)
        self._label_bg.setBrush(QBrush(QColor(255, 255, 255, 200)))
        self._label_bg.setPen(QPen(QColor(0, 0, 0, 80), 1))
        self._label_bg.setZValue(1)
        self._label_text = QGraphicsTextItem(self)
        self._label_text.setDefaultTextColor(QColor(20, 20, 20))
        self._label_text.setZValue(2)
        self.rebuild()

    @staticmethod
    def _center_of(it: TopoNodeItem) -> QPointF:
        r = it.boundingRect()
        p = it.pos()
        return QPointF(p.x() + r.width() / 2.0, p.y() + r.height() / 2.0)

    
    def rebuild(self):
        # If ports are defined in edge.meta, connect between ports; otherwise connect centers.
        meta = self.edge.meta or {}
        sp = meta.get("src_port")
        dp = meta.get("dst_port")
        if sp and dp:
            a = self.src_item.port_scene_pos(str(sp))
            b = self.dst_item.port_scene_pos(str(dp))
        else:
            a = self._center_of(self.src_item)
            b = self._center_of(self.dst_item)

        path = QPainterPath(a)
        lane_x = meta.get("lane_x")
        try:
            lane_x = float(lane_x) if lane_x is not None else a.x()
        except Exception:
            lane_x = a.x()

        if abs(a.x() - b.x()) < 1.0 and abs(lane_x - a.x()) < 1.0:
            path.lineTo(b)
        else:
            clearance = EDGE_CLEARANCE
            lane_step = max(4.0, MIN_LANE_GAP / 2.0)
            lane_offset = (sum(ord(c) for c in (self.edge.id or "")) % 7) * lane_step
            y1 = a.y() + clearance + lane_offset if b.y() >= a.y() else a.y() - clearance - lane_offset
            y2 = b.y() - clearance - lane_offset if b.y() >= a.y() else b.y() + clearance + lane_offset

            # 1) vertical from src
            if abs(a.y() - y1) > 0.5:
                path.lineTo(QPointF(a.x(), y1))
            # 2) horizontal to lane
            if abs(a.x() - lane_x) > 0.5:
                path.lineTo(QPointF(lane_x, y1))
            # 3) vertical down/up to target band
            if abs(y1 - y2) > 0.5:
                path.lineTo(QPointF(lane_x, y2))
            # 4) horizontal to dst (use slight offset to avoid shared horizontals)
            if abs(lane_x - b.x()) > 0.5:
                path.lineTo(QPointF(b.x(), y2))
            # 5) final to dst
            if abs(y2 - b.y()) > 0.5:
                path.lineTo(QPointF(b.x(), b.y()))
            else:
                path.lineTo(b)
        self.setPath(path)

        if self.isSelected():
            pen = QPen(QColor(30, 64, 175), 3)
        else:
            if (self.edge.circuit or "CA").upper() == "CC":
                pen = QPen(QColor(0, 120, 0), 2)
            else:
                pen = QPen(QColor(0, 0, 0), 2)
        pen.setStyle(Qt.SolidLine)
        self.setPen(pen)
        self._update_label()

    def _build_label_text(self) -> str:
        meta = self.edge.meta or {}
        d_m = meta.get("d_m")
        cond = meta.get("cond")
        s_val = meta.get("S")
        i_a = meta.get("I_A")
        dv = meta.get("dV_pct")
        dv_ac = meta.get("dV_ac_pct")

        lines = []
        parts1 = []
        if d_m is not None:
            try:
                parts1.append(f"d={float(d_m):.1f} m")
            except Exception:
                pass
        if cond:
            parts1.append(f"Cond={cond}")
        if parts1:
            lines.append(" | ".join(parts1))

        parts2 = []
        if s_val is not None:
            unit = "VA" if (self.edge.circuit or "CA").upper() == "CA" else "W"
            try:
                parts2.append(f"S={float(s_val):.0f} {unit}")
            except Exception:
                parts2.append(f"S={s_val} {unit}")
        if i_a is not None:
            try:
                parts2.append(f"I={float(i_a):.2f} A")
            except Exception:
                parts2.append(f"I={i_a} A")
        if parts2:
            lines.append(" | ".join(parts2))

        parts3 = []
        if dv is not None:
            try:
                parts3.append(f"ΔV={float(dv):.2f}%")
            except Exception:
                parts3.append(f"ΔV={dv}%")
        if dv_ac is not None:
            try:
                parts3.append(f"ΔV_ac={float(dv_ac):.2f}%")
            except Exception:
                parts3.append(f"ΔV_ac={dv_ac}%")
        if parts3:
            lines.append(" | ".join(parts3))

        return "\n".join(lines)

    def _update_label(self):
        text = self._build_label_text()
        if not text:
            self._label_text.setPlainText("")
            self._label_text.setVisible(False)
            self._label_bg.setVisible(False)
            return

        self._label_text.setPlainText(text)
        self._label_text.setVisible(True)
        self._label_bg.setVisible(True)

        br = self._label_text.boundingRect()
        pad = 4.0
        self._label_bg.setRect(br.adjusted(-pad, -pad, pad, pad))

        mid = self.path().pointAtPercent(0.5)
        x = mid.x() - (br.width() / 2.0)
        y = mid.y() - (br.height() / 2.0)
        self._label_text.setPos(QPointF(x, y))
        self._label_bg.setPos(QPointF(x, y))
