# -*- coding: utf-8 -*-
"""Controller para CabinetComponentsScreen.

Objetivo:
- Sacar del Screen operaciones de negocio/orquestación (copiar/pegar, sync modelo)
- Mantener el Screen enfocado en UI (widgets, signals y render)

Nota:
El controller *no* debe importar cabinet_screen.py (evita ciclos). Para constantes
de columnas usa screens.cabinet.constants.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Dict, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QComboBox, QTableWidgetItem

from ui.common import dialogs

from .constants import (
    COL_EQUIPO, COL_TAG, COL_MARCA, COL_MODELO, COL_P_W, COL_P_VA,
    COL_USAR_VA, COL_TIPO, COL_ORIGEN,
)


class CabinetController:
    def __init__(self, screen: Any):
        self.s = screen  # referencia al Screen (UI)
        self._emit_scheduled = False

    def _emit_data_changed_deferred(self) -> None:
        if self._emit_scheduled:
            return
        self._emit_scheduled = True
        QTimer.singleShot(0, self._emit_data_changed_once)

    def _emit_data_changed_once(self) -> None:
        self._emit_scheduled = False
        self.s.data_changed.emit()

    # -----------------------------
    # Copy/Paste de componentes
    # -----------------------------
    def copy_cabinet_components(self, source_cab: Optional[Dict[str, Any]], only_selected: bool = False):
        """Devuelve una lista deep-copiada de componentes, regenerando IDs."""
        if not source_cab:
            return []

        components = []
        for comp in source_cab.get("components", []):
            if only_selected and not comp.get("_selected", False):
                continue

            comp_copy = copy.deepcopy(comp)
            comp_copy["id"] = str(uuid.uuid4())

            # limpiar flags específicos (evita arrastrar selecciones de escenarios)
            data = comp_copy.setdefault("data", {})
            data.pop("cc_mom_incluir", None)
            data.pop("cc_mom_escenario", None)
            data.pop("cc_aleatorio_sel", None)

            components.append(comp_copy)

        return components

    def paste_cabinet_components(self, row: Optional[int] = None):
        """Pega en el gabinete destino los componentes copiados."""
        s = self.s
        if not getattr(s, "_copied_cabinet_components", None):
            dialogs.info(s, "Pegar consumos", "No hay consumos copiados para pegar.")
            return

        if row is None:
            row = s.cabinets_list.currentRow()
        if row < 0 or row >= len(s.cabinets):
            return

        dest_cabinet = s.cabinets[row]
        if not dest_cabinet:
            return

        # si el destino ya tiene componentes, confirmar reemplazo
        existing = dest_cabinet.get("components") or []
        if existing:
            if not dialogs.confirm(s, "Reemplazar consumos", "El gabinete destino ya tiene consumos. ¿Deseas reemplazarlos?", default_no=True):
                return

        new_comps = copy.deepcopy(s._copied_cabinet_components)
        for c in new_comps:
            if isinstance(c, dict):
                c["id"] = str(uuid.uuid4())

        dest_cabinet["components"] = new_comps

        # asegurar selección y refresco
        s.cabinets_list.setCurrentRow(row)
        s.current_cabinet = dest_cabinet

        if hasattr(s, '_pipeline'):
            s._pipeline.after_mutation(rebuild_view=True, emit=True, dirty=True)
        else:
            if hasattr(s.data_model, 'mark_dirty'):
                s.data_model.mark_dirty(True)
            s.update_design_view()
            self._emit_data_changed_deferred()

    # -----------------------------
    # Sync tabla -> modelo
    # -----------------------------
    def on_table_item_changed(self, item: QTableWidgetItem):
        s = self.s
        if getattr(s, "_loading", False):
            return
        row = item.row()
        col = item.column()
        if col not in (COL_TAG, COL_MARCA, COL_MODELO, COL_P_W, COL_P_VA):
            return

        id_item = s.table.item(row, COL_EQUIPO)
        if not id_item:
            return
        comp_id = id_item.data(Qt.UserRole)
        key_map = {
            COL_TAG: "tag",
            COL_MARCA: "marca",
            COL_MODELO: "modelo",
            COL_P_W: "potencia_w",
            COL_P_VA: "potencia_va",
        }
        key = key_map.get(col)
        if not key:
            return
        value = item.text()
        self.sync_from_table(comp_id, key, value)

    def sync_from_table(self, comp_id: str, key: str, value):
        s = self.s
        if not getattr(s, "current_cabinet", None):
            return

        s.data_model.mark_dirty(True)
        if hasattr(s.data_model, "invalidate_feeding_validation"):
            s.data_model.invalidate_feeding_validation()

        # actualizar componente en modelo
        for comp in s.current_cabinet.setdefault("components", []):
            if comp.get("id") == comp_id:
                data = s._normalize_comp_data(comp.setdefault("data", {}))
                if key == "usar_va":
                    data[key] = bool(value)
                else:
                    data[key] = value
                comp["data"] = data
                break

        # refrescos puntuales de UI (sin rearmar todo)
        for row in range(s.table.rowCount()):
            id_item = s.table.item(row, COL_EQUIPO)
            if not id_item or id_item.data(Qt.UserRole) != comp_id:
                continue

            if key == "marca":
                # si cambió marca, refrescar modelos
                s.on_brand_changed(row)
            elif key == "modelo":
                s.on_model_changed(row)
            elif key == "potencia_w":
                # recalcular modo potencia
                chk = s._get_checkbox_at(row, COL_USAR_VA)
                usar_va = bool(chk.isChecked()) if chk is not None else False
                tipo_widget = s.table.cellWidget(row, COL_TIPO)
                tipo_text = tipo_widget.currentText() if isinstance(tipo_widget, QComboBox) else ""
                s._apply_power_mode_to_row(row, usar_va, tipo_text)
            elif key == "potencia_va":
                chk = s._get_checkbox_at(row, COL_USAR_VA)
                usar_va = bool(chk.isChecked()) if chk is not None else False
                tipo_widget = s.table.cellWidget(row, COL_TIPO)
                tipo_text = tipo_widget.currentText() if isinstance(tipo_widget, QComboBox) else ""
                s._apply_power_mode_to_row(row, usar_va, tipo_text)
            elif key == "origen":
                s._apply_origin_to_row(row, value)

        self._emit_data_changed_deferred()
