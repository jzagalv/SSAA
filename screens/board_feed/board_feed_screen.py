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
from PyQt5.QtCore import Qt
from ui.table_utils import make_table_sortable
from screens.base import ScreenBase
from app.sections import Section



COL_TAG = 0
COL_DESC = 1
COL_CC_B1 = 2
COL_CC_B2 = 3
COL_CA_ES = 4
COL_CA_NOES = 5


class BoardFeedScreen(ScreenBase):
    SECTION = Section.BOARD_FEED
    def __init__(self, data_model, parent=None):
        super().__init__(data_model, parent=parent)
        self._loading = False
        self._row_map = []
        self._selected_row = -1

        self._setup_ui()
        self.load_from_model()

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

        for row in range(self.table.rowCount()):
            if not text:
                self.table.setRowHidden(row, False)
                continue

            item_tag = self.table.item(row, COL_TAG)
            item_desc = self.table.item(row, COL_DESC)

            tag_txt = item_tag.text().lower() if item_tag is not None else ""
            desc_txt = item_desc.text().lower() if item_desc is not None else ""

            match = text in tag_txt or text in desc_txt
            self.table.setRowHidden(row, not match)

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

        header = self.table.horizontalHeader()
        for col in range(self.table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        for col in range(self.table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.Interactive)

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
        try:
            gabinetes = getattr(self.data_model, "gabinetes", []) or []

            # --- Auto-detección de perfiles de alimentación ---
            # Esta pantalla se usa como "fuente" de alimentadores para Arquitectura SS/AA.
            # Por eso, además de los gabinetes, también debemos considerar consumos con
            # alimentador "Individual" (cada uno debe tener su propio alimentador).
            #
            # A partir del campo "tipo_consumo" (p.ej. "C.C. aleatorio", "C.A. Esencial"),
            # inferimos las columnas que deben quedar marcadas.

            def _infer_from_tipo(tipo: str) -> dict:
                """Inferir columnas a marcar desde un texto tipo 'C.C. aleatorio', 'C.A. Esencial', etc."""
                t = (tipo or "").strip().lower()
                flags = {
                    "cc_b1": False,
                    "cc_b2": False,
                    "ca_esencial": False,
                    "ca_no_esencial": False,
                }
                if not t:
                    return flags

                # CC: cualquier variante (aleatorio, etc.) => por defecto lo dejamos disponible en B1 y B2
                # para que esté disponible en ambas capas (el diseño final decide donde se conecta).
                if t.startswith("c.c") or t.startswith("cc") or "c.c" in t or t == "cc":
                    flags["cc_b1"] = True
                    flags["cc_b2"] = True
                    return flags

                # CA esencial / no esencial
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
                    alim = (d.get("alimentador") or "General").strip().lower()
                    if (alim == "individual") != bool(include_individual):
                        continue
                    tipo = d.get("tipo_consumo") or d.get("consumo") or ""
                    f = _infer_from_tipo(tipo)
                    for k in acc:
                        acc[k] = acc[k] or f.get(k, False)
                return acc


            def _pick_bool(obj: dict, key: str, inferred: bool) -> bool:
                """Usa el valor guardado si existe (aunque sea False). Si no existe, usa el inferido."""
                if isinstance(obj, dict) and key in obj:
                    return bool(obj.get(key))
                return bool(inferred)

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
            self._loading = False
            self.table.resizeColumnsToContents()
            self.table.resizeRowsToContents()

            if hasattr(self, "filter_edit"):
                self._apply_filter_text(self.filter_edit.text())

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

            if not any((g_cc_b1, g_cc_b2, g_ca_es, g_ca_noes)):
                issues.append(f"{ctx_g}: no tiene definida ninguna alimentación (marque al menos una).")

            comps = g.get("components", []) or []

            # --- Validación por tipo de consumo (C.C. / C.A.) ---
            # Determinamos qué tipos de consumo existen en el tablero.
            has_cc = False
            has_ca = False
            has_ca_es = False
            has_ca_no = False

            for c in comps:
                tc = str(c.get("tipo_consumo") or "").strip().lower()
                if tc.startswith("c.c."):
                    has_cc = True
                elif tc.startswith("c.a."):
                    has_ca = True
                    if "no" in tc:
                        has_ca_no = True
                    else:
                        has_ca_es = True

            # Si el tablero es SOLO C.C., no debería marcar C.A.
            if has_cc and not has_ca and (g_ca_es or g_ca_noes):
                issues.append(f"{ctx_g}: el tablero tiene consumos C.C. pero se marcó alimentación C.A. (Esencial/No esencial).")

            # Si el tablero es SOLO C.A., no debería marcar C.C.
            if has_ca and not has_cc and (g_cc_b1 or g_cc_b2):
                issues.append(f"{ctx_g}: el tablero tiene consumos C.A. pero se marcó alimentación C.C. (B1/B2).")

            # Requerimientos mínimos según lo que exista en el tablero.
            if has_cc and not (g_cc_b1 or g_cc_b2):
                issues.append(f"{ctx_g}: el tablero tiene consumos C.C. pero no se marcó ninguna alimentación C.C. (B1/B2).")
            if has_ca_es and not g_ca_es:
                issues.append(f"{ctx_g}: el tablero tiene consumos C.A. Esenciales pero no se marcó C.A. Esencial.")
            if has_ca_no and not g_ca_noes:
                issues.append(f"{ctx_g}: el tablero tiene consumos C.A. No esenciales pero no se marcó C.A. No esencial.")

            # Si el tablero NO tiene consumos de un tipo, marcarlo es inconsistencia.
            if not has_ca_es and g_ca_es:
                issues.append(f"{ctx_g}: se marcó C.A. Esencial pero el tablero no tiene consumos C.A. Esenciales.")
            if not has_ca_no and g_ca_noes:
                issues.append(f"{ctx_g}: se marcó C.A. No esencial pero el tablero no tiene consumos C.A. No esenciales.")
            for c in comps:
                if str(c.get("alimentador", "")).lower() != "individual":
                    continue
                ctag = c.get("tag") or c.get("id") or "(componente)"
                cdesc = c.get("descripcion") or ""
                ctx_c = f"{ctx_g} / Componente {ctag} ({cdesc})"

                # Validación tipo-consumo vs alimentación marcada a nivel consumo.
                tc = str(c.get("tipo_consumo") or "").strip().lower()

                data = c.get("data", {}) or {}
                c_cc_b1 = bool(data.get("feed_cc_b1", False))
                c_cc_b2 = bool(data.get("feed_cc_b2", False))
                c_ca_es = bool(data.get("feed_ca_esencial", False))
                c_ca_noes = bool(data.get("feed_ca_no_esencial", False))

                if tc.startswith("c.c") and (c_ca_es or c_ca_noes):
                    issues.append(f"{ctx_c}: es consumo C.C. pero tiene alimentación C.A. marcada.")
                if tc.startswith("c.a") and (c_cc_b1 or c_cc_b2):
                    issues.append(f"{ctx_c}: es consumo C.A. pero tiene alimentación C.C. marcada.")
                if tc.startswith("c.a"):
                    is_no = ("no" in tc)
                    if is_no and c_ca_es:
                        issues.append(f"{ctx_c}: es consumo C.A. No esencial pero se marcó C.A. Esencial.")
                    if (not is_no) and c_ca_noes:
                        issues.append(f"{ctx_c}: es consumo C.A. Esencial pero se marcó C.A. No esencial.")

                if not any((c_cc_b1, c_cc_b2, c_ca_es, c_ca_noes)):
                    issues.append(f"{ctx_c}: alimentador 'Individual' pero no tiene alimentación marcada.")
                    continue

                if c_cc_b1 and not g_cc_b1:
                    issues.append(f"{ctx_c}: usa C.C. B1 pero el gabinete NO tiene C.C. B1 marcado.")
                if c_cc_b2 and not g_cc_b2:
                    issues.append(f"{ctx_c}: usa C.C. B2 pero el gabinete NO tiene C.C. B2 marcado.")
                if c_ca_es and not g_ca_es:
                    issues.append(f"{ctx_c}: usa C.A. Esencial pero el gabinete NO tiene C.A. Esencial marcado.")
                if c_ca_noes and not g_ca_noes:
                    issues.append(f"{ctx_c}: usa C.A. No esencial pero el gabinete NO tiene C.A. No esencial marcado.")

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
