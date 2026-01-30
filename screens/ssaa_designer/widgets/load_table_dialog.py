# -*- coding: utf-8 -*-
"""LoadTableDialog widget extracted from ssaa_designer_screen.

UI-only dialog that shows a summary load table.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView
)


class LoadTableDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cuadro de cargas (resumen por tablero)")
        self.resize(700, 400)
        lay = QVBoxLayout(self)

        self.tbl = QTableWidget()
        self.tbl.setColumnCount(5)
        self.tbl.setHorizontalHeaderLabels(["Tablero", "Tipo", "Circuito", "Sistema DC", "P total [W]"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tbl.verticalHeader().setVisible(False)
        lay.addWidget(self.tbl)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.accept)
        btns.addWidget(self.btn_close)
        lay.addLayout(btns)

    def set_rows(self, rows):
        rows = rows or []
        self.tbl.setRowCount(len(rows))
        for r, (a, b, c, d, p) in enumerate(rows):
            vals = (a, b, c, d, f"{float(p):.0f}")
            for col, val in enumerate(vals):
                it = QTableWidgetItem(str(val))
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.tbl.setItem(r, col, it)
        self.tbl.resizeRowsToContents()
