# -*- coding: utf-8 -*-
"""screens.bank_charger.bank_charger_export

Utilidades de exportación/captura para BankChargerSizingScreen.

Extraído del módulo principal para reducir tamaño y mezclar menos responsabilidades.
Este módulo NO realiza cálculos: solo rendering/captura de widgets.
"""

from __future__ import annotations

import os
from typing import List, Tuple, Optional

from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QWidget,
    QTableWidget,
)
from ui.utils.capture_utils import (
    repolish_before_capture,
    grab_table_widget_full,
    grab_widget as _capture_grab_widget,
)


def grab_table_full(table: QTableWidget) -> Optional[QImage]:
    return grab_table_widget_full(table)


def grab_widget(widget: QWidget):
    """Devuelve un QPixmap o QImage listo para guardar, capturando tablas completas."""
    return _capture_grab_widget(widget)


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
    try:
        repolish_before_capture(screen)
    except Exception:
        import logging
        logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)


def save_widget_screenshot(screen, widget: QWidget, base_name: str = "captura") -> None:
    if widget is None:
        return

    _pre_capture(screen)
    try:
        repolish_before_capture(widget)
    except Exception:
        import logging
        logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)

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
        try:
            repolish_before_capture(widget)
        except Exception:
            import logging
            logging.getLogger(__name__).debug('Ignored exception (best-effort).', exc_info=True)
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
