from __future__ import annotations

from typing import Optional

from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QApplication, QWidget, QTableWidget, QTableView


def repolish_before_capture(widget: QWidget) -> None:
    try:
        if widget is None:
            return
        try:
            from ui.utils.style_utils import repolish_tree

            repolish_tree(widget)
        except Exception:
            pass
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
    except Exception:
        pass


def _grab_table_view_common(view: QTableView) -> Optional[QImage]:
    if view is None:
        return None

    h_header = view.horizontalHeader()
    v_header = view.verticalHeader()
    viewport = view.viewport()
    hbar = view.horizontalScrollBar()
    vbar = view.verticalScrollBar()

    total_w = int(h_header.length())
    total_h = int(v_header.length())
    out_w = int(v_header.width() + total_w + 2)
    out_h = int(h_header.height() + total_h + 2)

    if out_w <= 0 or out_h <= 0:
        try:
            return view.grab().toImage()
        except Exception:
            return None

    image = QImage(out_w, out_h, QImage.Format_ARGB32)
    try:
        image.fill(viewport.palette().base().color())
    except Exception:
        image.fill(view.palette().base().color())

    painter = QPainter(image)

    h_state = None
    v_state = None
    old_h = 0
    old_v = 0
    try:
        try:
            h_state = h_header.saveState()
        except Exception:
            h_state = None
        try:
            v_state = v_header.saveState()
        except Exception:
            v_state = None

        old_h = hbar.value()
        old_v = vbar.value()

        painter.save()
        painter.translate(v_header.width(), 0)
        h_header.render(painter)
        painter.restore()

        painter.save()
        painter.translate(0, h_header.height())
        v_header.render(painter)
        painter.restore()

        vp_w = max(1, viewport.width())
        vp_h = max(1, viewport.height())
        x_max = max(1, total_w)
        y_max = max(1, total_h)

        y = 0
        while y < y_max:
            vbar.setValue(y)
            app = QApplication.instance()
            if app is not None:
                app.processEvents()

            x = 0
            while x < x_max:
                hbar.setValue(x)
                app = QApplication.instance()
                if app is not None:
                    app.processEvents()

                painter.save()
                painter.translate(v_header.width() + x, h_header.height() + y)
                viewport.render(painter)
                painter.restore()
                x += vp_w

            y += vp_h
    finally:
        try:
            painter.end()
        except Exception:
            pass

        try:
            if h_state is not None:
                h_header.restoreState(h_state)
        except Exception:
            pass
        try:
            if v_state is not None:
                v_header.restoreState(v_state)
        except Exception:
            pass
        try:
            hbar.setValue(old_h)
            vbar.setValue(old_v)
            app = QApplication.instance()
            if app is not None:
                app.processEvents()
        except Exception:
            pass

    return image


def grab_table_widget_full(table: QTableWidget) -> Optional[QImage]:
    return _grab_table_view_common(table)


def grab_table_view_full(view: QTableView) -> Optional[QImage]:
    return _grab_table_view_common(view)


def grab_widget(widget: QWidget):
    if widget is None:
        return None
    if isinstance(widget, QTableWidget):
        img = grab_table_widget_full(widget)
        return img if img is not None else widget.grab()
    if isinstance(widget, QTableView):
        img = grab_table_view_full(widget)
        return img if img is not None else widget.grab()
    return widget.grab()
