# -*- coding: utf-8 -*-
"""screens.bank_charger.bank_charger_export

Utilidades de exportación/captura para BankChargerSizingScreen.

Extraído del módulo principal para reducir tamaño y mezclar menos responsabilidades.
Este módulo NO realiza cálculos: solo rendering/captura de widgets.
"""

from __future__ import annotations

import os
from typing import List, Tuple, Optional

from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QWidget,
    QTableWidget,
)


def grab_table_full(table: QTableWidget) -> Optional[QImage]:
    """Captura una QTableWidget completa (incluye headers) aunque tenga scroll."""
    if table is None:
        return None

    # Asegurar tamaños calculados
    try:
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
    except Exception:
        import logging
        logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

    h_header = table.horizontalHeader()
    v_header = table.verticalHeader()

    # Tamaño total del contenido real
    w = int(v_header.width() + h_header.length() + 2)
    h = int(h_header.height() + v_header.length() + 2)

    if w <= 0 or h <= 0:
        # fallback Qt
        shot = table.grab()
        # QPixmap; dejamos que el llamador lo guarde
        return shot.toImage()

    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(table.palette().base().color())

    painter = QPainter(img)

    # Render headers
    painter.save()
    painter.translate(v_header.width(), 0)
    h_header.render(painter)
    painter.restore()

    painter.save()
    painter.translate(0, h_header.height())
    v_header.render(painter)
    painter.restore()

    # Render celdas por "tiles" moviendo scrollbars
    viewport = table.viewport()
    vp_w = max(1, viewport.width())
    vp_h = max(1, viewport.height())

    hbar = table.horizontalScrollBar()
    vbar = table.verticalScrollBar()
    old_h = hbar.value()
    old_v = vbar.value()

    try:
        x_max = h_header.length()
        y_max = v_header.length()

        y = 0
        while y < y_max:
            vbar.setValue(y)
            QApplication.processEvents()

            x = 0
            while x < x_max:
                hbar.setValue(x)
                QApplication.processEvents()

                painter.save()
                painter.translate(v_header.width() + x, h_header.height() + y)
                viewport.render(painter)
                painter.restore()

                x += vp_w

            y += vp_h

    finally:
        hbar.setValue(old_h)
        vbar.setValue(old_v)
        QApplication.processEvents()

    painter.end()
    return img


def grab_widget(widget: QWidget):
    """Devuelve un QPixmap o QImage listo para guardar, capturando tablas completas."""
    if isinstance(widget, QTableWidget):
        return grab_table_full(widget)
    return widget.grab()


def default_capture_name(base: str) -> str:
    base = (base or "captura").strip().replace(" ", "_")
    return f"{base}.png"


def _pre_capture(screen) -> None:
    """Ejecuta hooks de commit/persistencia si existen en la pantalla."""
    # Antes de capturar: commit + persistencias (si existen)
    try:
        if hasattr(screen, "commit_pending_edits"):
            screen.commit_pending_edits()
        if hasattr(screen, "_save_perfil_cargas_to_model"):
            screen._save_perfil_cargas_to_model()
        if hasattr(screen, "_persist_ieee_kt_to_model"):
            screen._persist_ieee_kt_to_model()
    except Exception:
        import logging
        logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)


def save_widget_screenshot(screen, widget: QWidget, base_name: str = "captura") -> None:
    if widget is None:
        return

    _pre_capture(screen)

    suggested = default_capture_name(base_name)

    path, _ = QFileDialog.getSaveFileName(
        screen,
        "Guardar captura",
        suggested,
        "PNG (*.png);;JPEG (*.jpg *.jpeg)"
    )
    if not path:
        return

    shot = grab_widget(widget)

    ok = False
    if isinstance(shot, QImage):
        ok = shot.save(path)
    else:
        ok = shot.save(path)

    if not ok:
        QMessageBox.warning(screen, "Error", "No se pudo guardar la captura.")


def export_all_one_click(screen, items: List[Tuple[QWidget, str]]) -> None:
    """Exporta un set de widgets a una carpeta (un PNG por item)."""
    _pre_capture(screen)

    folder = QFileDialog.getExistingDirectory(screen, "Selecciona carpeta de exportación")
    if not folder:
        return

    def save_one(widget: QWidget, name: str) -> bool:
        path = os.path.join(folder, f"{name}.png")
        shot = grab_widget(widget)
        if isinstance(shot, QImage):
            return shot.save(path)
        return shot.save(path)

    ok_all = True
    for widget, name in items:
        ok_all &= save_one(widget, name)

    if not ok_all:
        QMessageBox.warning(screen, "Exportación", "Se exportó, pero al menos un archivo falló.")
    else:
        QMessageBox.information(screen, "Exportación", "Exportación completa.")
