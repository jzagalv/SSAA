# -*- coding: utf-8 -*-
"""ProjectFacade: typed-ish access over the persisted project dict.

Goals
- Concentrate schema defaults in one place.
- Hide raw dict keys from screens.
- Provide small, explicit methods used by controllers/services.

Notes
- This module MUST NOT depend on PyQt.
- Keep methods small and explicit; prefer adding a new method over leaking raw keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from core.keys import ProjectKeys as K


@dataclass
class ProjectFacade:
    data: Dict[str, Any]

    # ---------- generic ----------
    def _get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def _set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def ensure_dict(self, key: str) -> Dict[str, Any]:
        v = self.data.get(key)
        if not isinstance(v, dict):
            v = {}
            self.data[key] = v
        return v

    def ensure_list(self, key: str) -> List[Any]:
        v = self.data.get(key)
        if not isinstance(v, list):
            v = []
            self.data[key] = v
        return v

    # ---------- CC ----------
    def get_utilization_pct_global(self, default: float = 40.0) -> float:
        try:
            return float(self._get(K.UTILIZATION_PCT_GLOBAL, default))
        except Exception:
            return float(default)

    def set_utilization_pct_global(self, pct: float) -> None:
        self._set(K.UTILIZATION_PCT_GLOBAL, float(pct))

    def get_cc_use_pct_global(self, default: bool = True) -> bool:
        return bool(self._get(K.CC_USE_PCT_GLOBAL, default))

    def set_cc_use_pct_global(self, v: bool) -> None:
        self._set(K.CC_USE_PCT_GLOBAL, bool(v))

    def get_cc_scenarios(self) -> Dict[str, str]:
        v = self._get(K.CC_SCENARIOS, {}) or {}
        if not isinstance(v, dict):
            return {}
        out: Dict[str, str] = {}
        for k, val in v.items():
            out[str(k)] = ("" if val is None else str(val))
        return out

    def set_cc_scenarios(self, scenarios: Dict[str, str]) -> None:
        self._set(K.CC_SCENARIOS, dict(scenarios))

    def update_cc_scenario_desc(self, esc: str, desc: str) -> None:
        esc = str(esc)
        scenarios = self.get_cc_scenarios()
        scenarios[esc] = str(desc)
        self.set_cc_scenarios(scenarios)

    def get_cc_scenarios_enabled(self) -> Dict[str, bool]:
        v = self._get(K.CC_SCENARIOS_ENABLED, {}) or {}
        if not isinstance(v, dict):
            return {}
        out: Dict[str, bool] = {}
        for k, val in v.items():
            out[str(k)] = bool(val)
        return out

    def set_cc_scenarios_enabled(self, enabled_map: Dict[str, bool]) -> None:
        out: Dict[str, bool] = {}
        for k, val in (enabled_map or {}).items():
            out[str(k)] = bool(val)
        self._set(K.CC_SCENARIOS_ENABLED, out)

    def update_cc_scenario_enabled(self, esc: str, enabled: bool) -> None:
        esc = str(esc)
        enabled_map = self.get_cc_scenarios_enabled()
        enabled_map[esc] = bool(enabled)
        self.set_cc_scenarios_enabled(enabled_map)

    def get_cc_scenarios_summary(self) -> List[Dict[str, Any]]:
        v = self._get(K.CC_SCENARIOS_SUMMARY, [])
        return v if isinstance(v, list) else []

    def set_cc_scenarios_summary(self, summary: List[Dict[str, Any]]) -> None:
        self._set(K.CC_SCENARIOS_SUMMARY, list(summary))

    def get_cc_perm_pct_custom(self, default: float = 40.0) -> float:
        try:
            return float(self._get(K.CC_PERM_PCT_CUSTOM, default))
        except Exception:
            return float(default)

    def set_cc_perm_pct_custom(self, pct: float) -> None:
        self._set(K.CC_PERM_PCT_CUSTOM, float(pct))

    def get_cc_mom_include(self, default: bool = True) -> bool:
        return bool(self._get(K.CC_MOM_INCLUDE, default))

    def set_cc_mom_include(self, v: bool) -> None:
        self._set(K.CC_MOM_INCLUDE, bool(v))

    def get_cc_mom_scenario(self, default: str = "B1") -> str:
        v = self._get(K.CC_MOM_SCENARIO, default)
        return str(v) if v is not None else str(default)

    def set_cc_mom_scenario(self, scen: str) -> None:
        self._set(K.CC_MOM_SCENARIO, str(scen))

    def get_cc_random_sel(self, default: int = 0) -> int:
        try:
            return int(self._get(K.CC_RANDOM_SEL, default))
        except Exception:
            return int(default)

    def set_cc_random_sel(self, idx: int) -> None:
        self._set(K.CC_RANDOM_SEL, int(idx))

    # ---------- Designer ----------
    def get_ssaa_topology_legacy(self) -> Dict[str, Any]:
        """Legacy single-layer topology (K.SSAA_TOPOLOGY)."""
        v = self._get(K.SSAA_TOPOLOGY, {})
        return v if isinstance(v, dict) else {}

    def set_ssaa_topology_legacy(self, topo: Dict[str, Any]) -> None:
        self._set(K.SSAA_TOPOLOGY, dict(topo))

    def get_ssaa_topology_layers(self) -> Dict[str, Any]:
        v = self._get(K.SSAA_TOPOLOGY_LAYERS, {})
        return v if isinstance(v, dict) else {}

    def ensure_ssaa_topology_layer(self, workspace: str) -> Dict[str, Any]:
        layers = self.ensure_dict(K.SSAA_TOPOLOGY_LAYERS)
        ws = str(workspace or "CA_ES")
        layer = layers.get(ws)
        if not isinstance(layer, dict):
            layer = {"nodes": [], "edges": [], "used_feeders": []}
            layers[ws] = layer
        layer.setdefault("nodes", [])
        layer.setdefault("edges", [])
        layer.setdefault("used_feeders", [])
        return layer

    # ---------- Validation ----------
    def get_validation_issues(self) -> List[Dict[str, Any]]:
        v = self._get(K.VALIDATION_ISSUES, [])
        return v if isinstance(v, list) else []

    def set_validation_issues(self, issues: List[Dict[str, Any]]) -> None:
        self._set(K.VALIDATION_ISSUES, list(issues))
