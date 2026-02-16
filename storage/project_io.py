# -*- coding: utf-8 -*-
"""Project JSON I/O helpers.

These functions implement the actual read/write of project files.
DataModel keeps a thin wrapper API (save_to_file/load_from_file) that delegates here.

Keeping I/O out of the DataModel reduces its size and improves testability.
"""
from __future__ import annotations

import json
import os
import time
import logging
from typing import TYPE_CHECKING
from storage.project_paths import PROJECT_EXT
from infra.text_encoding import fix_mojibake_deep


def _count_items(value) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0


def _log_bank_charger_snapshot(data: dict, *, stage: str, file_path: str) -> None:
    proy = data.get("proyecto", {}) if isinstance(data.get("proyecto", {}), dict) else {}
    bc = proy.get("bank_charger", None)
    bc_dict = bc if isinstance(bc, dict) else {}
    logging.getLogger(__name__).info(
        "BankCharger %s snapshot file=%s has_bank_charger=%s perfil_root=%d perfil_bank=%d ale_root=%d ale_bank=%d",
        stage,
        file_path or "",
        isinstance(bc, dict),
        _count_items(proy.get("perfil_cargas")),
        _count_items(bc_dict.get("perfil_cargas")),
        _count_items(proy.get("cargas_aleatorias")),
        _count_items(bc_dict.get("cargas_aleatorias")),
    )


def _norm_project_path(folder: str, filename: str, ext: str = PROJECT_EXT) -> str:
    if not folder or not filename:
        return ""
    filename = filename.strip()
    folder = folder.strip()
    if not filename:
        return ""
    if not filename.lower().endswith(ext):
        filename = filename + ext
    return os.path.join(folder, filename)


def save_project(dm, file_path: str = "") -> bool:
    # Priority:
    # 1) explicit file_path
    # 2) dm.file_path (if opened/saved before)
    # 3) legacy folder+filename
    if not file_path:
        file_path = getattr(dm, "file_path", "") or ""
    if not file_path:
        file_path = _norm_project_path(getattr(dm, "project_folder", ""), getattr(dm, "project_filename", ""))
    if not file_path:
        raise ValueError("Archivo no definido. Usa 'Guardar como…' para escoger carpeta y nombre.")
    try:
        dm.file_path = file_path
        dm.project_folder = os.path.dirname(file_path)
        dm.project_filename = os.path.splitext(os.path.basename(file_path))[0]
        t0 = time.perf_counter()
        data = dm.to_dict()
        _log_bank_charger_snapshot(data, stage="save", file_path=file_path)
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        size_bytes = len(payload.encode("utf-8"))
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        logging.getLogger(__name__).debug(
            "Project serialize: %.1f ms, %d bytes", elapsed_ms, size_bytes
        )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(payload)
        if hasattr(dm, "mark_dirty"):
            dm.mark_dirty(False)
        else:
            dm.dirty = False
        if hasattr(dm, "notify_project_saved"):
            dm.notify_project_saved(file_path)
        return True
    except Exception as e:
        raise IOError(f"Error al guardar: {e}")


def load_project(dm, file_path: str) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data = fix_mojibake_deep(data)
        dm.from_dict(data, file_path=file_path)
        if hasattr(dm, "notify_project_loaded"):
            dm.notify_project_loaded(file_path)
        return True
    except Exception as e:
        raise IOError(f"Error al cargar: {e}")
