# -*- coding: utf-8 -*-
"""Workspace tabs builder for SSAA Designer.

Extracted from ssaa_designer_screen.py to keep the screen focused on UI wiring.
This module must NOT import ssaa_designer_screen (avoid circular imports).
"""

from __future__ import annotations

from typing import List

from PyQt5.QtWidgets import QWidget

from .feeders import iter_feed_rows

def available_workspaces(scr) -> List[str]:
    """Detect which workspaces (tabs) should exist based on 'Alimentación tableros'."""
    has_ca_es = False
    has_ca_noes = False
    has_cc_b1 = False
    has_cc_b2 = False

    for row in iter_feed_rows(scr):
        if row.get("ca_es"):
            has_ca_es = True
        if row.get("ca_noes"):
            has_ca_noes = True
        if row.get("cc_b1"):
            has_cc_b1 = True
        if row.get("cc_b2"):
            has_cc_b2 = True

    out: List[str] = []
    if has_ca_es:
        out.append("CA_ES")
    if has_ca_noes:
        out.append("CA_NOES")
    if has_cc_b1:
        out.append("CC_B1")
    if has_cc_b2:
        out.append("CC_B2")
    return out


def rebuild_workspace_tabs(scr) -> None:
    """Rebuild tabs according to available feeders, preserving current workspace if possible."""
    cur_ws = getattr(scr, "_workspace", None) or "CA_ES"

    scr.tabs.blockSignals(True)
    try:
        while scr.tabs.count() > 0:
            scr.tabs.removeTab(0)
        scr._workspace_tabs = []

        avail = available_workspaces(scr)
        if not avail:
            avail = ["CA_ES"]

        labels = {
            "CA_ES": "Esenciales",
            "CA_NOES": "No esenciales",
            "CC_B1": "CC.B1",
            "CC_B2": "CC.B2",
        }

        for ws in avail:
            w = QWidget()
            scr.tabs.addTab(w, labels.get(ws, ws))
            scr._workspace_tabs.append((ws, scr.tabs.count() - 1))

        ws_list = [k for k, _ in (scr._workspace_tabs or [])]
        if cur_ws in ws_list:
            scr._workspace = cur_ws
            for k, i in scr._workspace_tabs:
                if k == cur_ws:
                    scr.tabs.setCurrentIndex(i)
                    break
        else:
            scr._workspace = scr._workspace_tabs[0][0] if scr._workspace_tabs else "CA_ES"
            scr.tabs.setCurrentIndex(0)

        sync_layer_label(scr)
    finally:
        scr.tabs.blockSignals(False)


def on_workspace_tab_changed(scr, idx: int) -> None:
    """Handle tab change -> workspace change and reload current workspace."""
    ws = None
    for k, i in (scr._workspace_tabs or []):
        if i == idx:
            ws = k
            break
    if not ws:
        return
    if getattr(scr, "_workspace", None) == ws:
        return
    scr._workspace = ws
    sync_layer_label(scr)
    scr.reload_from_project()


def sync_layer_label(scr) -> None:
    labels = {
        "CA_ES": "CA / Esenciales",
        "CA_NOES": "CA / No esenciales",
        "CC_B1": "CC / B1",
        "CC_B2": "CC / B2",
    }
    if hasattr(scr, "lbl_layer"):
        scr.lbl_layer.setText(labels.get(getattr(scr, "_workspace", "CA_ES"), ""))