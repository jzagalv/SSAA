# -*- coding: utf-8 -*-
"""
DutyCyclePlotWidget
Encapsula el gráfico Matplotlib del ciclo de trabajo (duty cycle) para Bank/Charger sizing.

Objetivo del refactor (Paso 3B):
- Sacar el gráfico fuera de la pantalla principal para reducir tamaño del archivo UI.
- Mantener comportamiento idéntico (misma figura, leyenda y anotaciones A1..An y A(al)).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtWidgets import QWidget, QVBoxLayout

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


class DutyCyclePlotWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.fig = Figure(figsize=(5, 3))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def plot_from_segments(
        self,
        segs_real: List[Dict[str, Any]],
        sort_key: Callable[[str], Any],
        periods: Optional[List[Dict[str, Any]]] = None,
        rnd_cache: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Dibuja un stackplot del perfil de cargas a partir de segmentos (code, I, t0, t1, dur).

        - segs_real: lista de segmentos reales (incluye si corresponde el segmento aleatorio A(al)).
        - sort_key: función para ordenar códigos de carga.
        - periods: cache A1..An (t0/t1/label) para anotar encima de cada tramo.
        - rnd_cache: cache de A(al) (t0/t1/label) para anotar si aplica.
        """
        ax = self.ax
        ax.clear()
        ax.set_xlabel("Tiempo [min]")
        ax.set_ylabel("Corriente [A]")
        ax.set_title("Diagrama de ciclo de trabajo (duty cycle)")
        ax.grid(True, axis="y")

        if not segs_real:
            ax.text(0.5, 0.5, "Sin datos suficientes para graficar",
                    ha="center", va="center", transform=ax.transAxes)
            self.canvas.draw_idle()
            return

        # Tiempo máximo REAL
        x_max_real = max(float(s.get("t1", 0.0) or 0.0) for s in segs_real)
        x_max_real = max(x_max_real, 1.0)

        # Aire al final (sin alterar duraciones)
        last_seg = max(segs_real, key=lambda s: float(s.get("t1", 0.0)))
        last_dur_real = float(last_seg.get("dur", 0.0) or 0.0)
        extra = max(0.20 * last_dur_real, 50.0)
        x_max_plot = x_max_real + extra

        # Usamos duraciones REALES (sin reajuste)
        segs = []
        for s in segs_real:
            segs.append({
                "code": s["code"],
                "I": float(s["I"]),
                "t0": float(s["t0"]),
                "t1": float(s["t1"]),
                "dur": float(s.get("dur", float(s["t1"]) - float(s["t0"]))),
            })

        bps = {0.0, float(x_max_plot)}
        for s in segs:
            bps.add(s["t0"])
            bps.add(s["t1"])
        xs = sorted(bps)

        areas = sorted({s["code"] for s in segs}, key=sort_key)
        series = {a: [0.0] * len(xs) for a in areas}

        for i in range(len(xs) - 1):
            mid = (xs[i] + xs[i + 1]) / 2.0
            for s in segs:
                if s["t0"] <= mid < s["t1"]:
                    series[s["code"]][i] = s["I"]

        for a in areas:
            if len(xs) >= 2:
                series[a][-1] = series[a][-2]

        ys = [series[a] for a in areas]
        ax.stackplot(xs, *ys, labels=areas, step="post")

        totals = [sum(series[a][i] for a in areas) for i in range(len(xs))]
        y_max = max(totals) if totals else 0.0
        if y_max > 0:
            ax.set_ylim(0, y_max * 1.25)

        ax.set_xlim(0, x_max_plot)
        ax.legend(loc="upper right", fontsize=8)

        # Texto "A1, A2, ... A(al)" arriba de cada tramo
        def total_at(t: float) -> float:
            return sum(s["I"] for s in segs if s["t0"] <= t < s["t1"])

        y_pad = (y_max * 0.03) if y_max > 0 else 1.0

        for p in (periods or []):
            t0 = float(p.get("t0", 0.0))
            t1 = float(p.get("t1", 0.0))
            if t1 <= t0:
                continue
            mid = (t0 + t1) / 2.0
            yt = total_at(mid)
            ax.text(mid, yt + y_pad, str(p.get("label", "")),
                    ha="center", va="bottom", fontsize=10, fontweight="bold")

        if rnd_cache:
            t0 = float(rnd_cache.get("t0", 0.0))
            t1 = float(rnd_cache.get("t1", 0.0))
            if t1 > t0:
                mid = (t0 + t1) / 2.0
                yt = total_at(mid)
                ax.text(mid, yt + y_pad, str(rnd_cache.get("label", "A(al)")),
                        ha="center", va="bottom", fontsize=10, fontweight="bold")

        self.fig.tight_layout()
        self.canvas.draw_idle()
