# -*- coding: utf-8 -*-
"""Update pipeline para CabinetComponentsScreen.

Centraliza secuencias repetidas posteriores a mutaciones del modelo para evitar:
- duplicación (mark_dirty + update_design_view + emit)
- olvidos (no emitir data_changed, no redibujar)
- cambios inconsistentes entre paths (add/remove/paste/sync)

Regla:
- Los módulos externos NO deben usar @safe_slot (eso vive en el Screen).
- El pipeline no depende de Qt; usa solo el contrato del screen.
"""

from __future__ import annotations

from typing import Any


class CabinetUpdatePipeline:
    """Orquesta refrescos post-mutación en la pantalla Cabinet."""

    def __init__(self, screen: Any):
        self.s = screen

    # -----------------------------
    # Building blocks
    # -----------------------------
    def mark_dirty(self) -> None:
        dm = getattr(self.s, "data_model", None)
        if dm is not None and hasattr(dm, "mark_dirty"):
            dm.mark_dirty(True)

    def emit_changed(self) -> None:
        sig = getattr(self.s, "data_changed", None)
        if sig is not None:
            try:
                sig.emit()
            except Exception:
                # si el screen no expone signal real (tests), ignorar
                pass

    def rebuild_view(self) -> None:
        fn = getattr(self.s, "update_design_view", None)
        if callable(fn):
            fn()

    def ensure_scene_fits(self) -> None:
        fn = getattr(self.s, "_ensure_scene_fits", None)
        if callable(fn):
            fn()

    # -----------------------------
    # Public orchestrations
    # -----------------------------
    def after_mutation(self, *, rebuild_view: bool = True, emit: bool = True, dirty: bool = True) -> None:
        """Mutación de datos (agregar/quitar/pegar) -> marcar dirty + (opcional) redibujar + (opcional) emitir."""
        if dirty:
            self.mark_dirty()
        if rebuild_view:
            self.rebuild_view()
        if emit:
            self.emit_changed()

    def after_table_change(self, *, emit: bool = True, dirty: bool = True) -> None:
        """Cambio desde tabla: no redibuja (evita perder foco/edición), solo dirty + emit."""
        if dirty:
            self.mark_dirty()
        if emit:
            self.emit_changed()

    def after_card_move(self, *, dirty: bool = True) -> None:
        """Movimiento de tarjeta: solo ajustar scene + dirty (sin emit para mantener comportamiento)."""
        self.ensure_scene_fits()
        if dirty:
            self.mark_dirty()
