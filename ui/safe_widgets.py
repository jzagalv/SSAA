# -*- coding: utf-8 -*-
"""
Filtros y widgets "seguros" para la aplicación.
"""

from PyQt5.QtCore import QObject, QEvent
from PyQt5.QtWidgets import QComboBox


class ComboWheelFilter(QObject):
    """
    Filtro global que bloquea la rueda del mouse / gesto de scroll
    sobre TODOS los QComboBox de la aplicación.
    """
    def eventFilter(self, obj, event):
        # Si el objeto es un QComboBox y el evento es de rueda, lo bloqueamos
        if isinstance(obj, QComboBox) and event.type() == QEvent.Wheel:
            return True  # Evento consumido, no se propaga

        # Para todo lo demás, dejamos comportamiento normal
        return super().eventFilter(obj, event)
