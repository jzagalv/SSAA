# -*- coding: utf-8 -*-
"""storage/project_paths.py

Helpers de rutas y nombres de archivos de proyecto.

Este módulo NO depende de PyQt.
"""

from __future__ import annotations

import os


PROJECT_EXT = ".ssaa"


def norm_project_path(folder: str, filename: str, ext: str = PROJECT_EXT) -> str:
    """Construye un path de proyecto normalizado.

    - `filename` puede venir con o sin extensión.
    - Por defecto usamos `.ssaa` (archivo de proyecto de esta app).
    """
    folder = (folder or "").strip()
    filename = (filename or "").strip()
    if not folder:
        return ""

    ext = ext if ext.startswith(".") else f".{ext}"
    base, fext = os.path.splitext(filename)
    if fext.lower() == ext.lower():
        filename = base
    elif fext.lower() in (".json", ".ssaa"):
        filename = base
    return os.path.join(folder, f"{filename}{ext}")


def norm_json_path(folder: str, filename: str) -> str:
    """Backward-compat: nombre histórico."""
    return norm_project_path(folder, filename, ext=PROJECT_EXT)
