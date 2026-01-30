# table_utils.py
from PyQt5.QtWidgets import QTableWidget, QHeaderView, QWidget, QHBoxLayout
from PyQt5.QtCore import Qt


def make_table_sortable(table: QTableWidget):
    """
    Habilita el ordenamiento por columnas en un QTableWidget usando
    el comportamiento nativo de Qt:

    - Click en el encabezado: ordena por esa columna.
    - Vuelve a hacer click: invierte el orden (asc/desc).
    """

    if table is None:
        return

    # Estética consistente (muchas pantallas usan QTableWidget)
    # - filas alternadas
    # - selección por fila
    # - grilla activa (el color se controla vía QSS)
    table.setAlternatingRowColors(True)
    table.setShowGrid(True)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setSelectionMode(QTableWidget.SingleSelection)

    header: QHeaderView = table.horizontalHeader()

    # Permitimos clicks en el encabezado y mostramos el indicador
    header.setSectionsClickable(True)
    header.setSortIndicatorShown(True)

    # Dejamos que Qt se encargue de todo el ordenamiento
    table.setSortingEnabled(True)

    # Opcional: arrancar sin columna seleccionada (estético)
    header.setSortIndicator(-1, Qt.AscendingOrder)

def center_in_cell(widget: QWidget) -> QWidget:
    """
    Envuelve un widget para centrarlo dentro de una celda (QTableWidget).
    """
    container = QWidget()
    lay = QHBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setAlignment(Qt.AlignCenter)
    lay.addWidget(widget)
    return container
