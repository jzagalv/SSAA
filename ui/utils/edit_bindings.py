from __future__ import annotations

import logging
from typing import Callable

from PyQt5.QtCore import QEvent, QObject
from PyQt5.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
)

from ui.utils.undo_commands import ApplyValueCommand
from ui.utils.user_signals import (
    connect_combobox_user_changed,
    connect_lineedit_user_commit,
    connect_lineedit_user_live,
)

log = logging.getLogger(__name__)


def _repolish(w) -> None:
    try:
        if w is None:
            return
        style = w.style()
        if style is not None:
            style.unpolish(w)
            style.polish(w)
        w.update()
    except Exception:
        log.debug("_repolish failed (best-effort).", exc_info=True)


def mark_user_field(w) -> None:
    try:
        if w is not None:
            w.setProperty("userField", True)
            _repolish(w)
    except Exception:
        log.debug("mark_user_field failed (best-effort).", exc_info=True)


def set_invalid(w, invalid: bool, reason: str = "") -> None:
    try:
        if w is None:
            return
        w.setProperty("invalid", bool(invalid))
        w.setToolTip(str(reason or ""))
        _repolish(w)
    except Exception:
        log.debug("set_invalid failed (best-effort).", exc_info=True)


def set_invalid_spin(spin: QAbstractSpinBox, invalid: bool, reason: str = "") -> None:
    try:
        set_invalid(spin, invalid, reason)
    except Exception:
        log.debug("set_invalid_spin failed (best-effort).", exc_info=True)


def validate_lineedit(
    line: QLineEdit,
    *,
    required: bool = False,
    touched: bool = False,
    reason_required: str = "Campo obligatorio",
    reason_invalid: str = "Formato inválido",
) -> bool:
    try:
        if line is None:
            return True
        if touched:
            line.setProperty("_validation_touched", True)
        was_touched = bool(line.property("_validation_touched"))
        text = str(line.text() or "").strip()

        if not was_touched and not text:
            set_invalid(line, False, "")
            return True

        invalid = False
        reason = ""
        if required and was_touched and not text:
            invalid = True
            reason = str(reason_required or "Campo obligatorio")
        elif text and line.validator() is not None and not line.hasAcceptableInput():
            invalid = True
            reason = str(reason_invalid or "Formato inválido")

        set_invalid(line, invalid, reason)
        return not invalid
    except Exception:
        log.debug("validate_lineedit failed (best-effort).", exc_info=True)
        return True


def _get_widget_value(widget):
    try:
        if isinstance(widget, QLineEdit):
            return str(widget.text() or "")
        if isinstance(widget, QComboBox):
            return str(widget.currentText() or "")
        if isinstance(widget, QSpinBox):
            return int(widget.value())
        if isinstance(widget, QDoubleSpinBox):
            return float(widget.value())
        if isinstance(widget, QAbstractSpinBox) and hasattr(widget, "value"):
            return widget.value()
    except Exception:
        pass
    return ""


class _StartValueFilter(QObject):
    def eventFilter(self, obj, event):
        try:
            if event is None:
                return False
            et = event.type()
            if et in (QEvent.FocusIn, QEvent.MouseButtonPress):
                obj.setProperty("_undo_start_value", _get_widget_value(obj))
        except Exception:
            log.debug("_StartValueFilter failed (best-effort).", exc_info=True)
        return False


def _install_start_value_filter(widget) -> None:
    try:
        if widget is None:
            return
        flt = getattr(widget, "_start_value_filter", None)
        if flt is None:
            flt = _StartValueFilter(widget)
            setattr(widget, "_start_value_filter", flt)
            widget.installEventFilter(flt)
    except Exception:
        log.debug("install start-value filter failed (best-effort).", exc_info=True)


def bind_lineedit(
    line: QLineEdit,
    *,
    apply_fn: Callable[[str], None],
    undo_stack=None,
    title: str = "Change",
    ignore_if: Callable[[], bool] | None = None,
    required: bool = False,
    live_validate: bool = False,
) -> None:
    try:
        if line is None:
            return
        mark_user_field(line)
        _install_start_value_filter(line)
        line.setProperty("_undo_start_value", _get_widget_value(line))

        def _on_commit(_text: str) -> None:
            try:
                if ignore_if is not None and bool(ignore_if()):
                    return
                old_text = str(line.property("_undo_start_value") or "")
                new_text = str(line.text() or "")
                if old_text == new_text:
                    validate_lineedit(line, required=required, touched=True)
                    return
                if undo_stack is not None:
                    cmd = ApplyValueCommand(str(title or "Editar campo"), apply_fn, old_text, new_text)
                    try:
                        undo_stack.push(cmd)
                    except Exception:
                        apply_fn(new_text)
                else:
                    apply_fn(new_text)
                line.setProperty("_undo_start_value", str(line.text() or ""))
                validate_lineedit(line, required=required, touched=True)
            except Exception:
                log.debug("lineedit commit binding failed (best-effort).", exc_info=True)

        connect_lineedit_user_commit(line, _on_commit)

        if live_validate:
            connect_lineedit_user_live(
                line,
                lambda _txt: validate_lineedit(line, required=required, touched=True),
            )
    except Exception:
        log.debug("bind_lineedit failed (best-effort).", exc_info=True)


def bind_combobox(
    combo: QComboBox,
    *,
    apply_fn: Callable[[str], None],
    undo_stack=None,
    title: str = "Change",
    ignore_if: Callable[[], bool] | None = None,
) -> None:
    try:
        if combo is None:
            return
        mark_user_field(combo)
        _install_start_value_filter(combo)
        combo.setProperty("_undo_start_value", _get_widget_value(combo))

        def _on_changed(_text: str) -> None:
            try:
                if ignore_if is not None and bool(ignore_if()):
                    return
                old_text = str(combo.property("_undo_start_value") or "")
                new_text = str(combo.currentText() or "")
                if old_text == new_text:
                    return
                if undo_stack is not None:
                    cmd = ApplyValueCommand(str(title or "Editar campo"), apply_fn, old_text, new_text)
                    try:
                        undo_stack.push(cmd)
                    except Exception:
                        apply_fn(new_text)
                else:
                    apply_fn(new_text)
                combo.setProperty("_undo_start_value", str(combo.currentText() or ""))
            except Exception:
                log.debug("combobox binding failed (best-effort).", exc_info=True)

        connect_combobox_user_changed(combo, _on_changed)
    except Exception:
        log.debug("bind_combobox failed (best-effort).", exc_info=True)


def bind_checkbox(
    chk: QCheckBox,
    *,
    apply_fn: Callable[[bool], None],
    undo_stack=None,
    title: str = "Change",
    ignore_if: Callable[[], bool] | None = None,
) -> None:
    try:
        if chk is None:
            return
        mark_user_field(chk)
        chk.setProperty("_undo_start_value", bool(chk.isChecked()))

        def _handler(_checked: bool) -> None:
            try:
                if ignore_if is not None and bool(ignore_if()):
                    return
                new_value = bool(chk.isChecked())
                old_value = bool(chk.property("_undo_start_value"))
                if old_value == new_value:
                    return

                def _wrapper_apply(v: bool) -> None:
                    value = bool(v)
                    if bool(chk.isChecked()) != value:
                        blocked = chk.blockSignals(True)
                        try:
                            chk.setChecked(value)
                        finally:
                            chk.blockSignals(blocked)
                    apply_fn(value)
                    chk.setProperty("_undo_start_value", bool(chk.isChecked()))

                if undo_stack is not None:
                    cmd = ApplyValueCommand(str(title or "Editar campo"), _wrapper_apply, old_value, new_value)
                    try:
                        undo_stack.push(cmd)
                    except Exception:
                        _wrapper_apply(new_value)
                else:
                    apply_fn(new_value)

                chk.setProperty("_undo_start_value", bool(chk.isChecked()))
            except Exception:
                log.debug("checkbox binding failed (best-effort).", exc_info=True)

        chk.clicked.connect(_handler)
    except Exception:
        log.debug("bind_checkbox failed (best-effort).", exc_info=True)


def _values_equal(a, b, epsilon: float) -> bool:
    try:
        eps = float(epsilon)
    except Exception:
        eps = 0.0
    if eps <= 0.0:
        return a == b
    try:
        return abs(float(a) - float(b)) < eps
    except Exception:
        return a == b


def bind_spinbox(
    spin: QAbstractSpinBox,
    *,
    get_value: Callable[[], float | int],
    set_value: Callable[[float | int], None],
    apply_fn: Callable[[float | int], None],
    undo_stack=None,
    title: str = "Change",
    ignore_if: Callable[[], bool] | None = None,
    live_apply: bool = True,
    epsilon: float = 1e-9,
) -> None:
    try:
        if spin is None:
            return
        mark_user_field(spin)
        _install_start_value_filter(spin)
        try:
            spin.setProperty("_undo_start_value", get_value())
        except Exception:
            spin.setProperty("_undo_start_value", None)

        def _handle_live(v) -> None:
            try:
                if ignore_if is not None and bool(ignore_if()):
                    return
                if not bool(getattr(spin, "hasFocus", lambda: False)()):
                    return
                if not live_apply:
                    return
                apply_fn(v)
            except Exception:
                log.debug("spin live apply failed (best-effort).", exc_info=True)

        def _wrapper_apply(v: float | int) -> None:
            try:
                current = get_value()
            except Exception:
                current = None
            if _values_equal(current, v, epsilon):
                try:
                    spin.setProperty("_undo_start_value", get_value())
                except Exception:
                    pass
                return
            try:
                blocked = spin.blockSignals(True)
                try:
                    set_value(v)
                finally:
                    spin.blockSignals(blocked)
            except Exception:
                pass
            apply_fn(v)
            try:
                spin.setProperty("_undo_start_value", get_value())
            except Exception:
                pass

        def _handle_commit() -> None:
            try:
                if ignore_if is not None and bool(ignore_if()):
                    return
                old = spin.property("_undo_start_value")
                if old is None:
                    old = get_value()
                new = get_value()
                if _values_equal(new, old, epsilon):
                    return

                if undo_stack is not None:
                    if not live_apply:
                        try:
                            apply_fn(new)
                        except Exception:
                            log.debug("spin immediate apply failed (best-effort).", exc_info=True)
                    cmd = ApplyValueCommand(str(title or "Editar campo"), _wrapper_apply, old, new)
                    try:
                        undo_stack.push(cmd)
                    except Exception:
                        _wrapper_apply(new)
                else:
                    apply_fn(new)

                spin.setProperty("_undo_start_value", get_value())
            except Exception:
                log.debug("spin commit failed (best-effort).", exc_info=True)

        if isinstance(spin, QSpinBox):
            spin.valueChanged.connect(lambda v: _handle_live(int(v)))
        elif isinstance(spin, QDoubleSpinBox):
            spin.valueChanged.connect(lambda v: _handle_live(float(v)))
        elif hasattr(spin, "valueChanged"):
            spin.valueChanged.connect(_handle_live)

        if hasattr(spin, "editingFinished"):
            spin.editingFinished.connect(_handle_commit)
    except Exception:
        log.debug("bind_spinbox failed (best-effort).", exc_info=True)


def bind_lineedit_undo(
    line: QLineEdit,
    *,
    undo_stack,
    title: str,
    apply_fn: Callable[[str], None],
    ignore_if: Callable[[], bool] | None = None,
    required: bool = False,
    live_validate: bool = False,
) -> None:
    bind_lineedit(
        line,
        apply_fn=apply_fn,
        undo_stack=undo_stack,
        title=title,
        ignore_if=ignore_if,
        required=required,
        live_validate=live_validate,
    )


def bind_combobox_undo(
    combo: QComboBox,
    *,
    undo_stack,
    title: str,
    apply_fn: Callable[[str], None],
    ignore_if: Callable[[], bool] | None = None,
) -> None:
    bind_combobox(
        combo,
        apply_fn=apply_fn,
        undo_stack=undo_stack,
        title=title,
        ignore_if=ignore_if,
    )
