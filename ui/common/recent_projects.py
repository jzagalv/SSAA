from __future__ import annotations

import logging
import os

from ui.common.state import get_str, get_str_list, set_str, set_str_list

log = logging.getLogger(__name__)


class RecentProjectsStore:
    KEY_RECENTS = "project/recent_files"
    KEY_LAST_OPEN_DIR = "project/last_open_dir"
    KEY_LAST_SAVE_DIR = "project/last_save_dir"
    KEY_LAST_FOLDER_UI = "project/last_folder"
    KEY_LAST_NAME_UI = "project/last_filename"

    def __init__(self, limit: int = 10) -> None:
        try:
            self._limit = max(1, int(limit))
        except Exception:
            self._limit = 10

    def _normalize_path(self, path: str) -> str:
        value = str(path or "").strip()
        if not value:
            return ""
        try:
            return os.path.normpath(os.path.abspath(value))
        except Exception:
            return value

    def _read_all(self) -> list[str]:
        raw = get_str_list(self.KEY_RECENTS)
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            p = self._normalize_path(item)
            if not p or p in seen:
                continue
            seen.add(p)
            out.append(p)
        return out

    def list(self, existing_only: bool = True, prune_missing: bool = True) -> list[str]:
        paths = self._read_all()
        if not existing_only:
            return paths
        filtered: list[str] = []
        for p in paths:
            try:
                if os.path.exists(p):
                    filtered.append(p)
            except Exception:
                log.debug("Path existence check failed (%s)", p, exc_info=True)
        if prune_missing and filtered != paths:
            set_str_list(self.KEY_RECENTS, filtered)
        return filtered

    def push(self, file_path: str) -> list[str]:
        p = self._normalize_path(file_path)
        if not p:
            return self.list(existing_only=False)
        paths = [p] + self._read_all()
        out: list[str] = []
        seen: set[str] = set()
        for item in paths:
            if not item or item in seen:
                continue
            seen.add(item)
            out.append(item)
            if len(out) >= self._limit:
                break
        set_str_list(self.KEY_RECENTS, out)
        return out

    def remove(self, file_path: str) -> list[str]:
        p = self._normalize_path(file_path)
        if not p:
            return self.list(existing_only=False)
        out = [x for x in self._read_all() if x != p]
        set_str_list(self.KEY_RECENTS, out)
        return out

    def clear(self) -> None:
        set_str_list(self.KEY_RECENTS, [])

    def get_last_open_dir(self, default: str = "") -> str:
        return get_str(self.KEY_LAST_OPEN_DIR, default)

    def set_last_open_dir(self, path: str) -> None:
        set_str(self.KEY_LAST_OPEN_DIR, self._normalize_path(path))

    def get_last_save_dir(self, default: str = "") -> str:
        return get_str(self.KEY_LAST_SAVE_DIR, default)

    def set_last_save_dir(self, path: str) -> None:
        set_str(self.KEY_LAST_SAVE_DIR, self._normalize_path(path))

    def get_last_folder_ui(self, default: str = "") -> str:
        return get_str(self.KEY_LAST_FOLDER_UI, default)

    def set_last_folder_ui(self, path: str) -> None:
        normalized = self._normalize_path(path)
        set_str(self.KEY_LAST_FOLDER_UI, normalized)
        # Unificar fuente de última carpeta usada.
        set_str(self.KEY_LAST_OPEN_DIR, normalized)
        set_str(self.KEY_LAST_SAVE_DIR, normalized)

    def get_last_name_ui(self, default: str = "") -> str:
        return get_str(self.KEY_LAST_NAME_UI, default)

    def set_last_name_ui(self, name: str) -> None:
        set_str(self.KEY_LAST_NAME_UI, str(name or "").strip())
