# -*- coding: utf-8 -*-
"""services/ssaa_engine.py

Orquestación ÚNICA de cálculos SS/AA + validación.

- La UI debe llamar solo a este servicio (y no a domain directamente).
- No depende de PyQt.

Actualmente incluye el bloque "Banco y cargador" y deja ganchos para ampliar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from services.errors import Issue, Level

from domain.parse import to_float

from domain.ieee485 import build_ieee485
from domain.selection import compute_bank_selection, compute_charger_selection
from domain.bank_charger_engine import run_bank_charger_engine, BankChargerBundle
from services.load_tables_engine import build_ac_table, build_cc_table, list_board_nodes, ACRow, CCRow



@dataclass(frozen=True)
class LoadTablesBundle:
    """Cuadros de carga calculados a partir de la topología.

    Estructura:
      - ac_tables[workspace][board_node_id] -> List[ACRow]
      - cc_tables[workspace][board_node_id] -> List[CCRow]
      - totals: agregados simples para reportar y para alimentar cálculos DC
    """
    ac_tables: Dict[str, Dict[str, List[ACRow]]]
    cc_tables: Dict[str, Dict[str, List[CCRow]]]
    totals: Dict[str, Any]
    warnings: List[str] = None  # type: ignore

@dataclass(frozen=True)
class EngineResult:
    """Resultado de la ejecución del motor."""

    load_tables: Optional[LoadTablesBundle] = None
    bank_charger: Optional[BankChargerBundle] = None
    issues: List[Issue] = None  # type: ignore



class SSAAEngine:
    """Motor de orquestación.

    Hoy implementa: Banco y cargador (IEEE485 + selección).
    """

    def compute_load_tables(self, data_model) -> EngineResult:
        """Calcula cuadros CA/CC para todos los tableros detectados en la topología.

        No altera el modelo. Devuelve warnings/errores como `issues`.
        """
        issues: List[Issue] = []
        proyecto = getattr(data_model, "proyecto", {}) or {}

        workspaces = ["CA_ES", "CA_NOES", "CC_B1", "CC_B2"]

        ac_tables: Dict[str, Dict[str, List[ACRow]]] = {}
        cc_tables: Dict[str, Dict[str, List[CCRow]]] = {}

        # Validaciones de tensiones (solo warning por ahora; la tabla puede quedar en 0)
        v_mono = to_float(proyecto.get("tension_monofasica"), 0.0) or 0.0
        v_tri = to_float(proyecto.get("tension_trifasica"), 0.0) or 0.0
        v_dc = to_float(proyecto.get("tension_nominal"), 0.0) or 0.0

        if v_mono <= 0 or v_tri <= 0:
            issues.append(Issue(Level.WARNING, "AC_V_MISSING",
                                "Tensión CA mono/trifásica no definida: el cuadro CA puede quedar incompleto.",
                                field="proyecto.tension_monofasica|tension_trifasica"))
        if v_dc <= 0:
            issues.append(Issue(Level.WARNING, "DC_V_MISSING",
                                "Tensión DC nominal no definida: el cuadro CC puede quedar incompleto.",
                                field="proyecto.tension_nominal"))

        for ws in workspaces:
            boards = list_board_nodes(data_model, workspace=ws) or []
            if ws.startswith("CA"):
                ws_tables: Dict[str, List[ACRow]] = {}
                for node_id, _label in boards:
                    ws_tables[node_id] = build_ac_table(data_model, workspace=ws, board_node_id=node_id)
                ac_tables[ws] = ws_tables
            else:
                ws_tables2: Dict[str, List[CCRow]] = {}
                for node_id, _label in boards:
                    ws_tables2[node_id] = build_cc_table(data_model, workspace=ws, board_node_id=node_id)
                cc_tables[ws] = ws_tables2

        # Totales simples (útiles para reporte y para sugerir i_perm/i_evento)
        totals: Dict[str, Any] = {"ac": {}, "cc": {}}

        for ws, boards in ac_tables.items():
            t_ws = {"p_total_w": 0.0, "consumo_va": 0.0, "i_r": 0.0, "i_s": 0.0, "i_t": 0.0}
            for _bid, rows in boards.items():
                for r in rows:
                    t_ws["p_total_w"] += float(r.p_total_w or 0.0)
                    t_ws["consumo_va"] += float(r.consumo_va or 0.0)
                    t_ws["i_r"] += float(r.i_r or 0.0)
                    t_ws["i_s"] += float(r.i_s or 0.0)
                    t_ws["i_t"] += float(r.i_t or 0.0)
            totals["ac"][ws] = t_ws

        for ws, boards in cc_tables.items():
            t_ws = {"p_perm_w": 0.0, "i_perm_a": 0.0, "p_mom_w": 0.0, "i_mom_a": 0.0}
            for _bid, rows in boards.items():
                for r in rows:
                    t_ws["p_perm_w"] += float(r.p_perm_w or 0.0)
                    t_ws["i_perm_a"] += float(r.i_perm_a or 0.0)
                    t_ws["p_mom_w"] += float(r.p_mom_w or 0.0)
                    t_ws["i_mom_a"] += float(r.i_mom_a or 0.0)
            totals["cc"][ws] = t_ws

        bundle = LoadTablesBundle(ac_tables=ac_tables, cc_tables=cc_tables, totals=totals, warnings=[])
        return EngineResult(load_tables=bundle, bank_charger=None, issues=issues)

    def compute_all(
        self,
        *,
        data_model,
        periods: List[Dict[str, Any]],
        rnd: Optional[Dict[str, Any]] = None,
        i_perm: Optional[float] = None,
        cc_workspace_for_iperm: str = "CC_B1",
    ) -> EngineResult:
        """Facade principal: cuadros + banco/cargador + issues.

        - Primero calcula cuadros de carga.
        - Si i_perm no viene, sugiere i_perm desde el total permanente del workspace CC indicado.
        - Luego corre banco/cargador.
        """
        issues: List[Issue] = []

        # 1) Cuadros
        lt_res = self.compute_load_tables(data_model)
        issues.extend(lt_res.issues or [])

        load_tables = lt_res.load_tables

        # 2) i_perm sugerido
        proyecto = getattr(data_model, "proyecto", {}) or {}
        if i_perm is None:
            try:
                i_perm = float((load_tables.totals.get("cc", {}).get(cc_workspace_for_iperm, {}) or {}).get("i_perm_a", 0.0))
                if i_perm <= 0:
                    issues.append(Issue(Level.WARNING, "IPERM_ZERO",
                                        "i_perm calculado desde cuadro CC es 0 A. Revisa clasificación de cargas permanentes.",
                                        field="load_tables.totals.cc"))
            except Exception:
                i_perm = 0.0

        # 3) Banco/cargador
        bc_res = self.compute_bank_charger(
            proyecto=proyecto,
            periods=periods,
            rnd=rnd,
            i_perm=float(i_perm or 0.0),
        )
        issues.extend([i for i in (bc_res.issues or [])])

        return EngineResult(load_tables=load_tables, bank_charger=bc_res.bank_charger, issues=issues)


    def validate_project_for_bank_charger(self, proyecto: Dict[str, Any], *, periods: List[Dict[str, Any]]) -> List[Issue]:
        issues: List[Issue] = []
        v_nom = to_float(proyecto.get("tension_nominal", 0.0), 0.0) or 0.0
        if v_nom <= 0:
            issues.append(Issue(Level.ERROR, "V_NOM_MISSING", "Define la tensión nominal DC (tension_nominal).", field="proyecto.tension_nominal"))

        if not periods:
            issues.append(Issue(Level.ERROR, "DUTY_EMPTY", "El ciclo de trabajo (duty cycle) no tiene periodos.", field="bank_charger.periods"))
        else:
            for idx, p in enumerate(periods, start=1):
                if "A" not in p or "M" not in p:
                    issues.append(Issue(Level.ERROR, "DUTY_BAD_ROW", f"Periodo {idx} incompleto: se requiere A y M.", field=f"bank_charger.periods[{idx}]"))

        # Kt mode
        kt_mode = str(proyecto.get("kt_mode", "MANUAL") or "MANUAL").upper()
        if kt_mode not in ("MANUAL", "IEEE_CURVE", "MANUFACTURER"):
            issues.append(Issue(Level.WARNING, "KT_MODE_UNKNOWN", f"kt_mode='{kt_mode}' no reconocido. Usando MANUAL.", field="proyecto.kt_mode"))

        return issues

    def _build_kt_store(self, proyecto: Dict[str, Any], *, periods: List[Dict[str, Any]]) -> tuple[Dict[str, Any], List[Issue]]:
        """Construye el store de Kt para IEEE485.

        Soporte actual:
        - MANUAL: usa proyecto['ieee485_kt']

        Futuro (diseñado, pero aún sin implementación numérica):
        - IEEE_CURVE: calcula Kt con curva IEEE (requiere final V/celda)
        - MANUFACTURER: calcula Kt desde tabla del fabricante (A vs Vfinal/celda)
        """
        issues: List[Issue] = []
        kt_mode = str(proyecto.get("kt_mode", "MANUAL") or "MANUAL").upper()

        if kt_mode == "MANUAL":
            store = proyecto.get("ieee485_kt", None)
            if not isinstance(store, dict):
                store = {}
                proyecto["ieee485_kt"] = store
            return store, issues

        # --- No-manual modes ---
        final_vpc = proyecto.get("kt_final_vpc", None)
        if final_vpc in (None, ""):
            issues.append(Issue(Level.ERROR, "KT_FINAL_VPC_MISSING", "Para calcular Kt automáticamente debes indicar el voltaje final por celda (kt_final_vpc).", field="proyecto.kt_final_vpc"))
        else:
            try:
                float(str(final_vpc).replace(",", "."))
            except Exception:
                issues.append(Issue(Level.ERROR, "KT_FINAL_VPC_BAD", "kt_final_vpc no es numérico.", field="proyecto.kt_final_vpc"))

        if kt_mode == "IEEE_CURVE":
            issues.append(Issue(Level.WARNING, "KT_IEEE_NOT_IMPL", "Kt por curva IEEE: estructura lista, pero falta implementar la curva/algoritmo.", field="proyecto.kt_mode"))
            return {}, issues

        if kt_mode == "MANUFACTURER":
            issues.append(Issue(Level.WARNING, "KT_MFG_NOT_IMPL", "Kt por datos del fabricante: estructura lista, pero falta implementar lectura/interpolación de tabla.", field="proyecto.kt_mode"))
            return {}, issues

        # fallback
        issues.append(Issue(Level.WARNING, "KT_MODE_FALLBACK", "Modo Kt no reconocido; se usará store vacío.", field="proyecto.kt_mode"))
        return {}, issues

    def compute_bank_charger(
        self,
        *,
        proyecto: Dict[str, Any],
        periods: List[Dict[str, Any]],
        rnd: Optional[Dict[str, Any]],
        i_perm: float,
    ) -> EngineResult:
        issues: List[Issue] = []

        issues.extend(self.validate_project_for_bank_charger(proyecto, periods=periods))

        kt_store, kt_issues = self._build_kt_store(proyecto, periods=periods)
        issues.extend(kt_issues)

        # Si hay errores críticos, no seguimos.
        if any(i.level == Level.ERROR for i in issues):
            return EngineResult(bank_charger=None, issues=issues)

        bundle = run_bank_charger_engine(
            proyecto=proyecto,
            periods=periods,
            rnd=rnd,
            kt_store=kt_store,
            i_perm=i_perm,
            build_ieee485_fn=build_ieee485,
            compute_bank_selection_fn=compute_bank_selection,
            compute_charger_selection_fn=compute_charger_selection,
        )

        # warnings internos del bundle -> issues WARNING
        for w in (bundle.warnings or []):
            issues.append(Issue(Level.WARNING, "ENGINE_WARN", w))

        return EngineResult(bank_charger=bundle, issues=issues)