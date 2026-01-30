# -*- coding: utf-8 -*-
"""License recovery dialog (cloud mode).

Shown when the app cannot start due to license issues and no grace is available.
Allows the user to retry online validation without closing the app abruptly.
"""
from __future__ import annotations

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt

from services.license_service import check_license


class LicenseRecoveryDialog(QDialog):
    def __init__(self, reason: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SSAA - Recuperación de licencia")
        self.setModal(True)
        self.setMinimumWidth(520)

        v = QVBoxLayout(self)
        self.lbl = QLabel(self._format_reason(reason))
        self.lbl.setWordWrap(True)
        self.lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self.lbl)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        v.addWidget(self.status)

        row = QHBoxLayout()
        self.btn_retry = QPushButton("Revalidar ahora")
        self.btn_exit = QPushButton("Salir")
        row.addWidget(self.btn_retry)
        row.addStretch(1)
        row.addWidget(self.btn_exit)
        v.addLayout(row)

        self.btn_retry.clicked.connect(self._retry)
        self.btn_exit.clicked.connect(self.reject)

    @staticmethod
    def _format_reason(reason: str) -> str:
        return (
            "No se pudo iniciar SSAA porque la licencia no está disponible y no hay período de gracia.\n\n"
            f"Detalle: {reason}\n\n"
            "Acción recomendada: verifica conexión a internet y vuelve a intentar."
        )

    def _retry(self) -> None:
        self.status.setText("Validando en línea...")
        st = check_license(force_online=True)
        if st.ok:
            self.accept()
            return
        self.status.setText("❌ No se pudo validar.\n\n" + str(st.reason))
