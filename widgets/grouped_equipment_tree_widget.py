# -*- coding: utf-8 -*-
"""Collapsible grouped equipment tree for Cabinet/Consumos."""

from __future__ import annotations

import json
from typing import Dict, Iterable

from PyQt5.QtCore import Qt, QMimeData, pyqtSignal
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem

try:
    from screens.cabinet.graphics.view import MIME_CONSUMO
except Exception:  # pragma: no cover - safe fallback
    MIME_CONSUMO = "application/x-ssaa-consumo"


class GroupedEquipmentTreeWidget(QTreeWidget):
    """Tree grouped by C.C/C.A and subcategories."""

    equipmentActivated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setItemsExpandable(True)
        self.setExpandsOnDoubleClick(True)
        self.setSelectionMode(QTreeWidget.SingleSelection)
        self.setDragEnabled(True)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.itemActivated.connect(self._on_item_activated)
        self._build_static_groups()

    def _build_static_groups(self) -> None:
        self.clear()
        self._groups: Dict[tuple[str, str], QTreeWidgetItem] = {}

        cc = QTreeWidgetItem(["C.C."])
        ca = QTreeWidgetItem(["C.A."])
        self.addTopLevelItem(cc)
        self.addTopLevelItem(ca)

        cc_perm = QTreeWidgetItem(["Permanentes"])
        cc_mom = QTreeWidgetItem(["Momentáneos"])
        cc_ale = QTreeWidgetItem(["Aleatorios"])
        cc.addChildren([cc_perm, cc_mom, cc_ale])

        ca_ess = QTreeWidgetItem(["Esenciales"])
        ca_no_ess = QTreeWidgetItem(["No esenciales"])
        ca.addChildren([ca_ess, ca_no_ess])

        self._groups[("C.C.", "Permanentes")] = cc_perm
        self._groups[("C.C.", "Momentáneos")] = cc_mom
        self._groups[("C.C.", "Aleatorios")] = cc_ale
        self._groups[("C.A.", "Esenciales")] = ca_ess
        self._groups[("C.A.", "No esenciales")] = ca_no_ess

        self.expandAll()

    def _resolve_group(self, tipo_consumo: str) -> tuple[str, str]:
        tipo = str(tipo_consumo or "").strip().lower()
        if tipo.startswith("c.a."):
            if "no esencial" in tipo:
                return "C.A.", "No esenciales"
            return "C.A.", "Esenciales"
        if "moment" in tipo:
            return "C.C.", "Momentáneos"
        if "aleat" in tipo:
            return "C.C.", "Aleatorios"
        return "C.C.", "Permanentes"

    @staticmethod
    def _is_equipment_item(item: QTreeWidgetItem) -> bool:
        payload = item.data(0, Qt.UserRole)
        return isinstance(payload, dict) and bool(str(payload.get("name", "")).strip())

    def set_items(self, items: Iterable[dict]) -> None:
        self._build_static_groups()

        for raw in items or []:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name", "")).strip()
            if not name:
                continue

            payload = {
                "name": name,
                "lib_uid": str(raw.get("lib_uid", "") or ""),
                "code": str(raw.get("code", "") or ""),
                "tipo_consumo": str(raw.get("tipo_consumo", "") or ""),
                "origen": str(raw.get("origen", "") or ""),
            }
            top, subgroup = self._resolve_group(payload["tipo_consumo"])
            parent = self._groups.get((top, subgroup))
            if parent is None:
                continue

            leaf = QTreeWidgetItem([name])
            leaf.setData(0, Qt.UserRole, payload)
            leaf.setFlags(leaf.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            parent.addChild(leaf)

        self.expandAll()

    def _activate_if_equipment(self, item: QTreeWidgetItem) -> None:
        if item is None or not self._is_equipment_item(item):
            return
        payload = item.data(0, Qt.UserRole)
        self.equipmentActivated.emit(dict(payload))

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        self._activate_if_equipment(item)

    def _on_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        self._activate_if_equipment(item)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item is None or not self._is_equipment_item(item):
            return

        payload = item.data(0, Qt.UserRole) or {}
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(payload.get("name", "") or ""))
        try:
            mime.setData(MIME_CONSUMO, json.dumps(payload).encode("utf-8"))
        except Exception:
            import logging
            logging.getLogger(__name__).debug("Ignored exception (best-effort).", exc_info=True)
        drag.setMimeData(mime)
        drag.exec_(supportedActions)

