# -*- coding: utf-8 -*-
"""
Pestaña de distribución de alimentación de tableros (versión simplificada).

- Fila general por cada gabinete.
- Filas adicionales por cada componente con 'alimentador' == "Individual".
- Para cada fila se pueden marcar:
    * C.C. B1
    * C.C. B2
    * C.A. Esencial
    * C.A. No esencial

Sin columnas de "Tablero Padre".
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QPushButton, QMessageBox,
    QDialog, QAbstractItemView, QLineEdit, QListWidget
)
from PyQt5.QtCore import Qt, QTimer, QSignalBlocker
import logging
from ui.table_utils import make_table_sortable
from ui.utils.table_utils import configure_table_autoresize
from screens.base import ScreenBase
from app.sections import Section



COL_TAG = 0
COL_DESC = 1
COL_CC_B1 = 2
COL_CC_B2 = 3
COL_CA_ES = 4
COL_CA_NOES = 5


def _get_comp_alimentador(comp: dict) -> str:
    d = (comp or {}).get("data") or {}
    raw = d.get("alimentador")
    if raw is None or str(raw).strip() == "":
        raw = (comp or {}).get("alimentador")
    if raw is None or str(raw).strip() == "":
        raw = "General"
    return str(raw).strip().lower()


def _infer_from_tipo(tipo: str) -> dict:
    t = (tipo or "").strip().lower()
    flags = {"cc_b1": False, "cc_b2": False, "ca_esencial": False, "ca_no_esencial": False}

    if not t:
        return flags

    if t.startswith("c.c") or t.startswith("cc") or "c.c" in t or t == "cc":
        flags["cc_b1"] = True
        flags["cc_b2"] = True
        return flags

    if "c.a" in t or t.startswith("ca"):
        if "no" in t and "esencial" in t:
            flags["ca_no_esencial"] = True
        elif "esencial" in t:
            flags["ca_esencial"] = True

    return flags


def _infer_from_components(components, include_individual: bool) -> dict:
    acc = {"cc_b1": False, "cc_b2": False, "ca_esencial": False, "ca_no_esencial": False}

    for comp in components or []:
        d = (comp or {}).get("data", {}) or {}

        alim = _get_comp_alimentador(comp)
        if include_individual:
            if alim != "individual":
                continue
        else:
            if alim == "individual":
                continue

        tipo = d.get("tipo_consumo") or d.get("consumo") or ""
        f = _infer_from_tipo(tipo)

        for k in acc:
            acc[k] = acc[k] or bool(f.get(k, False))

    return acc


def _pick_bool(obj: dict, key: str, inferred: bool) -> bool:
    if isinstance(obj, dict) and key in obj:
        return bool(obj.get(key))
    return bool(inferred)


class BoardFeedScreen(ScreenBase):
    SECTION = Section.BOARD_FEED
    def __init__(self, data_model, parent=None):
        super().__init__(data_model, parent=parent)
        self._loading = False
        self._row_map = []
        self._selected_row = -1
        self._issues_timer = QTimer(self)
        self._issues_timer.setSingleShot(True)
        self._issues_timer.timeout.connect(self._update_issue_count)
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.timeout.connect(self._reload_from_model_debounced)

        self._setup_ui()
        self.load_from_model()
        if hasattr(self.data_model, "on"):
            self.data_model.on("section_changed", self._on_section_changed)
            self.data_model.on("feeding_validation_invalidated", self._on_feeding_validation_invalidated)

    def _restyle(self, w: QWidget):
        w.style().unpolish(w)
        w.style().polish(w)
        w.update()

    def _set_state(self, w: QWidget, state: str):
        w.setProperty("state", state)
        self._restyle(w)

    def _update_row_widget_styles(self):
        row = self.table.currentRow()
        if row == self._selected_row:
            return

        # limpiar fila anterior
        if self._selected_row >= 0:
            for col in range(self.table.columnCount()):
                cellw = self.table.cellWidget(self._selected_row, col)
                if cellw is None:
                    continue
                self._set_state(cellw, "normal")

        # aplicar estado a fila nueva
        self._selected_row = row
        if row < 0:
            return

        for col in range(self.table.columnCount()):
            cellw = self.table.cellWidget(row, col)
            if cellw is None:
                continue
            self._set_state(cellw, "selected")

    # ---------------------------------------------------------
    # Filtro por TAG / Descripción
    # ---------------------------------------------------------
    def _apply_filter_text(self, text: str):
        """Oculta las filas cuyo TAG o Descripción no contengan el texto dado."""
        text = (text or "").strip().lower()
        rows = self.table.rowCount()
        cols = self.table.columnCount()
        if rows <= 0 or cols <= 0:
            return

        for row in range(rows):
            if not text:
                self.table.setRowHidden(row, False)
                continue

            item_tag = self.table.item(row, COL_TAG) if COL_TAG < cols else None
            item_desc = self.table.item(row, COL_DESC) if COL_DESC < cols else None

            if item_tag is not None or item_desc is not None:
                tag_txt = item_tag.text().lower() if item_tag is not None else ""
                desc_txt = item_desc.text().lower() if item_desc is not None else ""
                hay = f"{tag_txt} {desc_txt}".strip()
            else:
                parts = []
                for c in range(cols):
                    it = self.table.item(row, c)
                    if it is not None:
                        parts.append(it.text())
                hay = " ".join(parts).lower()

            match = text in hay
            self.table.setRowHidden(row, not match)

    def _iter_consumptions(self, gab):
        for comp in (gab.get("components") or []):
            data = (comp or {}).get("data", {}) or {}
            tipo = (
                data.get("tipo_consumo")
                or data.get("consumo")
                or comp.get("tipo_consumo")
                or comp.get("consumo")
                or ""
            )
            yield str(tipo).strip().lower()

    def _has_cc_consumptions(self, gab) -> bool:
        for t in self._iter_consumptions(gab):
            if t.startswith("c.c") or t.startswith("cc") or "c.c" in t:
                return True
        return False

    def _has_ca_essential(self, gab) -> bool:
        for t in self._iter_consumptions(gab):
            if "c.a" in t or t.startswith("ca"):
                if "no" in t and "esencial" in t:
                    continue
                if "esencial" in t:
                    return True
        return False

    def _has_ca_no_essential(self, gab) -> bool:
        for t in self._iter_consumptions(gab):
            if "c.a" in t or t.startswith("ca"):
                if "no" in t and "esencial" in t:
                    return True
        return False

    def _iter_consumptions_for_target(self, gab, comp_index):
        if gab is None:
            return []
        if comp_index is None:
            return list(self._iter_consumptions(gab))
        comps = gab.get("components", []) or []
        if not (0 <= comp_index < len(comps)):
            return []
        comp = comps[comp_index]
        data = (comp or {}).get("data", {}) or {}
        tipo = (
            data.get("tipo_consumo")
            or data.get("consumo")
            or comp.get("tipo_consumo")
            or comp.get("consumo")
            or ""
        )
        return [str(tipo).strip().lower()]

    def _has_cc_from_types(self, types_list) -> bool:
        for t in types_list or []:
            if t.startswith("c.c") or t.startswith("cc") or "c.c" in t:
                return True
        return False

    def _has_ca_essential_from_types(self, types_list) -> bool:
        for t in types_list or []:
            if "c.a" in t or t.startswith("ca"):
                if "no" in t and "esencial" in t:
                    continue
                if "esencial" in t:
                    return True
        return False

    def _has_ca_no_essential_from_types(self, types_list) -> bool:
        for t in types_list or []:
            if "c.a" in t or t.startswith("ca"):
                if "no" in t and "esencial" in t:
                    return True
        return False

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Distribución de alimentación de tableros"))

        btn_row = QHBoxLayout()
        self.btn_validate = QPushButton("Validar inconsistencias")
        self.btn_validate.clicked.connect(self.show_validation_dialog)
        btn_row.addWidget(self.btn_validate)
        self.btn_auto_assign = QPushButton("Asignación automática...")
        self.btn_auto_assign.clicked.connect(self._show_auto_assign_dialog)
        btn_row.addWidget(self.btn_auto_assign)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        filter_row = QHBoxLayout()
        lbl_filter = QLabel("Filtrar (Tag / Descripción):")
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Escribe para filtrar...")
        self.filter_edit.textChanged.connect(self._apply_filter_text)
        filter_row.addWidget(lbl_filter)
        filter_row.addWidget(self.filter_edit)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels([
            "Tag", "Descripción",
            "C.C. B1", "C.C. B2",
            "C.A. Esencial", "C.A. No esencial",
        ])

        for col in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(col)
            item.setTextAlignment(Qt.AlignCenter)

        # Sin selección de filas (evita el relleno verde por selección y reduce "clicks" accidentales)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)

        configure_table_autoresize(self.table)

        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        make_table_sortable(self.table)
        layout.addWidget(self.table)

    # ---------------------------------------------------------
    # Carga de datos
    # ---------------------------------------------------------
    def load_from_model(self):
        """Populate UI from current DataModel."""
        self.load_data()

    def save_to_model(self):
        """This screen is read-mostly; kept for API consistency."""
        return

    def load_data(self):
        """Rellena la tabla desde self.data_model.gabinetes (sin tableros padre)."""
        self._loading = True
        scroll_y = self.table.verticalScrollBar().value()
        cur_row = self.table.currentRow()
        cur_col = self.table.currentColumn()
        blocker = None
        try:
            gabinetes = getattr(self.data_model, "gabinetes", []) or []
            blocker = QSignalBlocker(self.table)

            # --- Auto-detección de perfiles de alimentación ---
            # Esta pantalla se usa como "fuente" de alimentadores para Arquitectura SS/AA.
            # Por eso, además de los gabinetes, también debemos considerar consumos con
            # alimentador "Individual" (cada uno debe tener su propio alimentador).
            #
            # A partir del campo "tipo_consumo" (p.ej. "C.C. aleatorio", "C.A. Esencial"),
            # inferimos las columnas que deben quedar marcadas.

            self.table.setRowCount(0)
            self._row_map = []

            current_row = 0

            for cab_index, g in enumerate(gabinetes):
                tag_gab = str(g.get("tag", ""))
                desc_gab = str(g.get("nombre", g.get("descripcion", "")) or "")

                # 1) Fila general del gabinete
                self.table.insertRow(current_row)
                self._row_map.append((cab_index, None))

                it_tag = QTableWidgetItem(tag_gab)
                it_tag.setData(Qt.UserRole, (cab_index, None))
                it_tag.setFlags(it_tag.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(current_row, COL_TAG, it_tag)

                it_desc = QTableWidgetItem(desc_gab)
                it_desc.setFlags(it_desc.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(current_row, COL_DESC, it_desc)

                # Auto-inferir perfil del gabinete a partir de sus componentes "Generales"
                comps = g.get("components", []) or []
                infer_g = _infer_from_components(comps, include_individual=False)

                # IMPORTANTE:
                # Antes se hacía: stored OR inferred. Eso rompe el guardado porque
                # si el usuario desmarca (False) pero la inferencia da True, al
                # recargar vuelve a aparecer marcado.
                # Regla nueva: si el campo existe en JSON, se respeta SIEMPRE.
                # Si no existe, usamos la inferencia como valor inicial.
                cc_b1 = bool(g["cc_b1"]) if "cc_b1" in g else bool(infer_g["cc_b1"])
                cc_b2 = bool(g["cc_b2"]) if "cc_b2" in g else bool(infer_g["cc_b2"])
                ca_es = bool(g["ca_esencial"]) if "ca_esencial" in g else bool(infer_g["ca_esencial"])
                ca_noes = bool(g["ca_no_esencial"]) if "ca_no_esencial" in g else bool(infer_g["ca_no_esencial"])

                # Persistir (para que Arquitectura SS/AA vea consistencia sin depender de la UI)
                g["cc_b1"] = cc_b1
                g["cc_b2"] = cc_b2
                g["ca_esencial"] = ca_es
                g["ca_no_esencial"] = ca_noes

                self._add_checkbox(current_row, COL_CC_B1, cc_b1, "cc_b1")
                self._add_checkbox(current_row, COL_CC_B2, cc_b2, "cc_b2")
                self._add_checkbox(current_row, COL_CA_ES, ca_es, "ca_esencial")
                self._add_checkbox(current_row, COL_CA_NOES, ca_noes, "ca_no_esencial")

                current_row += 1

                # 2) Filas individuales (requieren alimentador propio)
                for comp_index, comp in enumerate(comps):
                    data = comp.setdefault("data", {})
                    comp_alim = str(data.get("alimentador", comp.get("alimentador", "")) or "").strip().lower()
                    if comp_alim != "individual":
                        continue

                    # Nota: el consumo individual puede tener su propio tag/id, pero en esta pantalla
                    # la columna TAG debe mostrar SIEMPRE el TAG del tablero/gabinete.
                    # El vínculo al consumo individual se mantiene en Qt.UserRole.
                    desc_c = str(comp.get("descripcion") or comp.get("name") or comp.get("nombre") or "")

                    self.table.insertRow(current_row)
                    self._row_map.append((cab_index, comp_index))

                    # Columna TAG: siempre el TAG del tablero/gabinete.
                    # (El vínculo al consumo individual se mantiene en UserRole).
                    it_tag_c = QTableWidgetItem(tag_gab)
                    it_tag_c.setData(Qt.UserRole, (cab_index, comp_index))
                    it_tag_c.setFlags(it_tag_c.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(current_row, COL_TAG, it_tag_c)

                    # Descripción enriquecida para identificar el consumo individual.
                    # Ej: "Gabinete ... / Motores ..."
                    it_desc_c = QTableWidgetItem(f"{desc_gab} / {desc_c}" if desc_gab else desc_c)
                    it_desc_c.setFlags(it_desc_c.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(current_row, COL_DESC, it_desc_c)

                    # Auto-inferir perfil del consumo Individual (su propio alimentador)
                    tipo_c = str(data.get("tipo_consumo") or data.get("consumo") or "")
                    infer_c = _infer_from_tipo(tipo_c)

                    # Misma regla que en gabinetes: si el usuario ya definió el flag,
                    # se respeta aunque el inferido sea True.
                    cc_b1_c = bool(data.get("feed_cc_b1")) if "feed_cc_b1" in data else bool(infer_c["cc_b1"])
                    cc_b2_c = bool(data.get("feed_cc_b2")) if "feed_cc_b2" in data else bool(infer_c["cc_b2"])
                    ca_es_c = bool(data.get("feed_ca_esencial")) if "feed_ca_esencial" in data else bool(infer_c["ca_esencial"])
                    ca_noes_c = bool(data.get("feed_ca_no_esencial")) if "feed_ca_no_esencial" in data else bool(infer_c["ca_no_esencial"])

                    # Persistir flags en el propio componente (para que aparezca como alimentador disponible)
                    data["feed_cc_b1"] = cc_b1_c
                    data["feed_cc_b2"] = cc_b2_c
                    data["feed_ca_esencial"] = ca_es_c
                    data["feed_ca_no_esencial"] = ca_noes_c

                    self._add_checkbox(current_row, COL_CC_B1, cc_b1_c, "feed_cc_b1")
                    self._add_checkbox(current_row, COL_CC_B2, cc_b2_c, "feed_cc_b2")
                    self._add_checkbox(current_row, COL_CA_ES, ca_es_c, "feed_ca_esencial")
                    self._add_checkbox(current_row, COL_CA_NOES, ca_noes_c, "feed_ca_no_esencial")

                    current_row += 1

        finally:
            if blocker is not None:
                del blocker
            self._loading = False
            configure_table_autoresize(self.table)
            self.table.resizeRowsToContents()

            if hasattr(self, "filter_edit"):
                self._apply_filter_text(self.filter_edit.text())
            self._schedule_issue_count_update()

            try:
                self.table.verticalScrollBar().setValue(scroll_y)
            except Exception:
                pass
            if cur_row >= 0 and cur_col >= 0 and cur_row < self.table.rowCount():
                try:
                    self.table.setCurrentCell(cur_row, cur_col)
                except Exception:
                    pass

    # ---------------------------------------------------------
    # Helpers para widgets en celdas
    # ---------------------------------------------------------
    def _row_from_cell_widget(self, w: QWidget) -> int:
        if w is None:
            return -1
        pos = w.mapTo(self.table.viewport(), w.rect().center())
        idx = self.table.indexAt(pos)
        return idx.row() if idx.isValid() else -1

    def _add_checkbox(self, row, col, checked: bool, key: str):
        chk = QCheckBox()
        chk.setChecked(checked)
        chk.setProperty("data_key", key)
        chk.stateChanged.connect(self._on_checkbox_changed)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(chk)
        layout.addStretch()

        self.table.setCellWidget(row, col, container)

    # ---------------------------------------------------------
    # Handlers de cambios
    # ---------------------------------------------------------
    def _get_target_from_row(self, row):
        if row < 0 or row >= self.table.rowCount():
            return None, None, None

        item_tag = self.table.item(row, COL_TAG)
        if item_tag is None:
            return None, None, None

        key = item_tag.data(Qt.UserRole)
        if not key or not isinstance(key, tuple) or len(key) != 2:
            return None, None, None

        cab_index, comp_index = key

        gabinetes = getattr(self.data_model, "gabinetes", []) or []
        if not (0 <= cab_index < len(gabinetes)):
            return None, None, None

        gab = gabinetes[cab_index]
        if comp_index is None:
            return gab, None, gab

        comps = gab.get("components", []) or []
        if not (0 <= comp_index < len(comps)):
            return None, None, None

        target = comps[comp_index].setdefault("data", {})
        return gab, comp_index, target

    def _on_checkbox_changed(self, state: int):
        if self._loading:
            return

        chk = self.sender()
        if not isinstance(chk, QCheckBox):
            return

        key = chk.property("data_key")
        if not key:
            return

        container = chk.parent()
        if container is None:
            return

        row = self._row_from_cell_widget(container)
        if row < 0:
            return

        gab, comp_index, target_data = self._get_target_from_row(row)
        if target_data is None:
            return

        target_data[key] = (state == Qt.Checked)

        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)
        self._schedule_issue_count_update()

    # ---------------------------------------------------------
    # Auto-assign
    # ---------------------------------------------------------
    def _show_auto_assign_dialog(self):
        if self._loading:
            return
        dlg = AutoAssignDialog(self, self._compute_auto_assign_diffs)
        if dlg.exec_() != QDialog.Accepted:
            return
        diffs = dlg.get_diffs()
        if not diffs:
            return
        self._apply_auto_assign_diffs(diffs)

    def _compute_auto_assign_diffs(self, only_inconsistencies: bool):
        diffs = []
        gabinetes = getattr(self.data_model, "gabinetes", []) or []
        for row, (cab_index, comp_index) in enumerate(self._row_map):
            if not (0 <= cab_index < len(gabinetes)):
                continue
            gab = gabinetes[cab_index]
            if comp_index is None:
                key_cc_b1, key_cc_b2 = "cc_b1", "cc_b2"
                key_ca_es, key_ca_no = "ca_esencial", "ca_no_esencial"
                target_data = gab
            else:
                comps = gab.get("components", []) or []
                if not (0 <= comp_index < len(comps)):
                    continue
                target_data = comps[comp_index].setdefault("data", {})
                key_cc_b1, key_cc_b2 = "feed_cc_b1", "feed_cc_b2"
                key_ca_es, key_ca_no = "feed_ca_esencial", "feed_ca_no_esencial"

            types_list = self._iter_consumptions_for_target(gab, comp_index)
            has_cc = self._has_cc_from_types(types_list)
            has_ca_es = self._has_ca_essential_from_types(types_list)
            has_ca_no = self._has_ca_no_essential_from_types(types_list)

            cur_cc_b1 = bool(target_data.get(key_cc_b1, False))
            cur_cc_b2 = bool(target_data.get(key_cc_b2, False))
            cur_ca_es = bool(target_data.get(key_ca_es, False))
            cur_ca_no = bool(target_data.get(key_ca_no, False))

            inconsistent = (
                (has_cc and not (cur_cc_b1 or cur_cc_b2)) or
                ((not has_cc) and (cur_cc_b1 or cur_cc_b2)) or
                (has_ca_es and not cur_ca_es) or
                ((not has_ca_es) and cur_ca_es) or
                (has_ca_no and not cur_ca_no) or
                ((not has_ca_no) and cur_ca_no)
            )
            if only_inconsistencies and not inconsistent:
                continue

            target_cc_b1 = True if has_cc else False
            target_cc_b2 = cur_cc_b2 if has_cc else False
            target_ca_es = True if has_ca_es else False
            target_ca_no = True if has_ca_no else False

            if (
                cur_cc_b1 == target_cc_b1 and
                cur_cc_b2 == target_cc_b2 and
                cur_ca_es == target_ca_es and
                cur_ca_no == target_ca_no
            ):
                continue

            tag = ""
            desc = ""
            it_tag = self.table.item(row, COL_TAG)
            it_desc = self.table.item(row, COL_DESC)
            if it_tag is not None:
                tag = it_tag.text()
            if it_desc is not None:
                desc = it_desc.text()

            diffs.append({
                "row": row,
                "cab_index": cab_index,
                "comp_index": comp_index,
                "tag": tag,
                "desc": desc,
                "keys": (key_cc_b1, key_cc_b2, key_ca_es, key_ca_no),
                "before": (cur_cc_b1, cur_cc_b2, cur_ca_es, cur_ca_no),
                "after": (target_cc_b1, target_cc_b2, target_ca_es, target_ca_no),
            })

        return diffs

    def _apply_auto_assign_diffs(self, diffs):
        gabinetes = getattr(self.data_model, "gabinetes", []) or []
        if not diffs:
            return
        logger = logging.getLogger(__name__)
        logger.debug("Applying board feed auto-assign for %s rows", len(diffs))

        with QSignalBlocker(self.table):
            for d in diffs:
                cab_index = d.get("cab_index")
                comp_index = d.get("comp_index")
                if cab_index is None or not (0 <= cab_index < len(gabinetes)):
                    continue
                gab = gabinetes[cab_index]
                if comp_index is None:
                    target_data = gab
                else:
                    comps = gab.get("components", []) or []
                    if not (0 <= comp_index < len(comps)):
                        continue
                    target_data = comps[comp_index].setdefault("data", {})

                key_cc_b1, key_cc_b2, key_ca_es, key_ca_no = d.get("keys")
                after = d.get("after") or (False, False, False, False)
                target_data[key_cc_b1] = bool(after[0])
                target_data[key_cc_b2] = bool(after[1])
                target_data[key_ca_es] = bool(after[2])
                target_data[key_ca_no] = bool(after[3])

                row = d.get("row", -1)
                if row >= 0:
                    self._set_checkbox_cell(row, COL_CC_B1, bool(after[0]))
                    self._set_checkbox_cell(row, COL_CC_B2, bool(after[1]))
                    self._set_checkbox_cell(row, COL_CA_ES, bool(after[2]))
                    self._set_checkbox_cell(row, COL_CA_NOES, bool(after[3]))

        if hasattr(self.data_model, "mark_dirty"):
            self.data_model.mark_dirty(True)
        self._schedule_issue_count_update()

    def _set_checkbox_cell(self, row: int, col: int, checked: bool):
        cell = self.table.cellWidget(row, col)
        if cell is None:
            return
        chk = cell.findChild(QCheckBox)
        if chk is None:
            return
        chk.blockSignals(True)
        chk.setChecked(bool(checked))
        chk.blockSignals(False)

    def _schedule_issue_count_update(self):
        if self._issues_timer.isActive():
            self._issues_timer.start(200)
        else:
            self._issues_timer.start(200)

    def _update_issue_count(self):
        count = len(self._collect_issues())
        self.btn_validate.setText(f"Validar inconsistencias ({count})")

    def _reload_from_model_debounced(self):
        self.load_from_model()

    def _on_section_changed(self, section):
        if section in (Section.CABINET, Section.INSTALACIONES):
            if self._reload_timer.isActive():
                self._reload_timer.start(250)
            else:
                self._reload_timer.start(250)

    def _on_feeding_validation_invalidated(self):
        self._schedule_issue_count_update()

    # ---------------------------------------------------------
    # Validación
    # ---------------------------------------------------------
    def show_validation_dialog(self):
        issues = self._collect_issues()
        if not issues:
            QMessageBox.information(
                self,
                "Validación de alimentación",
                "No se encontraron inconsistencias en la alimentación de tableros.",
            )
            return

        dlg = FeedValidationDialog(issues, self)
        dlg.exec_()

    def _collect_issues(self):
        """Inconsistencias detectadas (sin tableros padre)."""
        issues = []
        gabinetes = getattr(self.data_model, "gabinetes", []) or []

        for g in gabinetes:
            tag = g.get("tag", "(sin tag)")
            desc = g.get("nombre", "")
            ctx_g = f"Gabinete {tag} ({desc})"

            g_cc_b1 = bool(g.get("cc_b1", False))
            g_cc_b2 = bool(g.get("cc_b2", False))
            g_ca_es = bool(g.get("ca_esencial", False))
            g_ca_noes = bool(g.get("ca_no_esencial", False))

            has_cc = self._has_cc_consumptions(g)
            has_ca_es = self._has_ca_essential(g)
            has_ca_no = self._has_ca_no_essential(g)
            if has_cc and not (g_cc_b1 or g_cc_b2):
                issues.append(f"{ctx_g}: tiene consumos C.C. pero no está asignado a CC.B1 ni CC.B2.")
            if has_ca_es and not g_ca_es:
                issues.append(f"{ctx_g}: tiene consumos C.A. esenciales pero no está asignado a barra C.A. Esencial.")
            if has_ca_no and not g_ca_noes:
                issues.append(f"{ctx_g}: tiene consumos C.A. no esenciales pero no está asignado a barra C.A. No esencial.")
            if g_ca_es and not has_ca_es:
                issues.append(f"{ctx_g}: está asignado a C.A. Esencial pero no tiene consumos esenciales.")
            if g_ca_noes and not has_ca_no:
                issues.append(f"{ctx_g}: está asignado a C.A. No esencial pero no tiene consumos no esenciales.")
            if (has_cc or has_ca_es or has_ca_no) and not any((g_cc_b1, g_cc_b2, g_ca_es, g_ca_noes)) and not bool(g.get("is_energy_source", False)):
                issues.append(f"{ctx_g}: no tiene definida ninguna alimentación (marque al menos una).")

        return issues

    def showEvent(self, event):
        """Refresca automáticamente al entrar a la pestaña.

        Así evitamos el botón manual de "Actualizar consumos".
        """
        super().showEvent(event)
        # Evitamos refrescar si estamos en medio de una carga (por seguridad).
        if not self._loading:
            self.load_from_model()


class FeedValidationDialog(QDialog):
    def __init__(self, issues, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Validación de alimentación de tableros")
        self.resize(800, 400)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Se encontraron {len(issues)} inconsistencias en la alimentación:"))

        self.list = QListWidget()
        self.list.addItems(issues)
        layout.addWidget(self.list)

        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class AutoAssignDialog(QDialog):
    def __init__(self, parent, compute_fn):
        super().__init__(parent)
        self.setWindowTitle("Asignación automática")
        self.resize(800, 420)
        self._compute_fn = compute_fn
        self._diffs = []

        layout = QVBoxLayout(self)
        self.lbl_summary = QLabel("")
        layout.addWidget(self.lbl_summary)

        self.chk_only_incons = QCheckBox("Aplicar solo a inconsistencias")
        self.chk_only_incons.setChecked(True)
        self.chk_only_incons.toggled.connect(self._refresh_preview)
        layout.addWidget(self.chk_only_incons)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Tag", "Antes", "Después"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        configure_table_autoresize(self.table)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_apply = QPushButton("Aplicar")
        self.btn_apply.clicked.connect(self._on_apply)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

        self._refresh_preview()

    def _refresh_preview(self):
        only_incons = bool(self.chk_only_incons.isChecked())
        self._diffs = self._compute_fn(only_incons)
        self.table.setRowCount(0)

        flag_changes = 0
        rows_changed = len(self._diffs)

        for d in self._diffs:
            before = d.get("before") or (False, False, False, False)
            after = d.get("after") or (False, False, False, False)
            flag_changes += sum(1 for a, b in zip(before, after) if a != b)

            row = self.table.rowCount()
            self.table.insertRow(row)
            tag = d.get("tag") or ""
            desc = d.get("desc") or ""
            label = tag if not desc else f"{tag} - {desc}"
            self.table.setItem(row, 0, QTableWidgetItem(label))
            self.table.setItem(row, 1, QTableWidgetItem(self._format_flags(before)))
            self.table.setItem(row, 2, QTableWidgetItem(self._format_flags(after)))

        if rows_changed <= 0:
            self.lbl_summary.setText("No hay cambios a aplicar.")
            self.btn_apply.setEnabled(False)
        else:
            self.lbl_summary.setText(
                f"Se aplicarán cambios en {rows_changed} fila(s), "
                f"modificando {flag_changes} marca(s) de alimentación."
            )
            self.btn_apply.setEnabled(True)

        configure_table_autoresize(self.table)

    @staticmethod
    def _format_flags(flags):
        cc_b1, cc_b2, ca_es, ca_no = flags
        return (
            f"CC.B1={'✓' if cc_b1 else '✗'}  "
            f"CC.B2={'✓' if cc_b2 else '✗'}  "
            f"CA.E={'✓' if ca_es else '✗'}  "
            f"CA.NE={'✓' if ca_no else '✗'}"
        )

    def _on_apply(self):
        if not self._diffs:
            self.reject()
            return
        self.accept()

    def get_diffs(self):
        return list(self._diffs or [])
