from __future__ import annotations

import logging

from ui.common.state import (
    get_int,
    restore_header_state,
    restore_splitter_state,
    save_header_state,
    save_splitter_state,
    set_int,
)

log = logging.getLogger(__name__)


class UiStateBinder:
    def __init__(self) -> None:
        self._headers: dict[str, object] = {}
        self._splitters: dict[str, object] = {}
        self._tabs: dict[str, object] = {}

    def bind_header(self, header, key: str):
        self._headers[str(key)] = header
        return self

    def bind_splitter(self, splitter, key: str):
        self._splitters[str(key)] = splitter
        return self

    def bind_tab_index(self, tab_widget, key: str):
        self._tabs[str(key)] = tab_widget
        return self

    # Backward-compatible alias
    def bind_tab(self, tab_widget, key: str):
        return self.bind_tab_index(tab_widget, key)

    def restore(self) -> None:
        for key, header in list(self._headers.items()):
            try:
                restore_header_state(header, key)
            except Exception:
                log.debug("restore header failed (%s)", key, exc_info=True)
        for key, splitter in list(self._splitters.items()):
            try:
                restore_splitter_state(splitter, key)
            except Exception:
                log.debug("restore splitter failed (%s)", key, exc_info=True)
        for key, tab_widget in list(self._tabs.items()):
            try:
                idx = int(get_int(key, int(tab_widget.currentIndex())))
                if 0 <= idx < int(tab_widget.count()):
                    tab_widget.setCurrentIndex(idx)
            except Exception:
                log.debug("restore tab failed (%s)", key, exc_info=True)

    def persist(self) -> None:
        for key, header in list(self._headers.items()):
            try:
                save_header_state(header, key)
            except Exception:
                log.debug("persist header failed (%s)", key, exc_info=True)
        for key, splitter in list(self._splitters.items()):
            try:
                save_splitter_state(splitter, key)
            except Exception:
                log.debug("persist splitter failed (%s)", key, exc_info=True)
        for key, tab_widget in list(self._tabs.items()):
            try:
                set_int(key, int(tab_widget.currentIndex()))
            except Exception:
                log.debug("persist tab failed (%s)", key, exc_info=True)
