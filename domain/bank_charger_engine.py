# domain/bank_charger_engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List

from .parse import to_float, is_blank

@dataclass(frozen=True)
class BankChargerBundle:
    # IEEE
    ieee: Any  # resultado de build_ieee485(...)
    missing_kt_keys: List[str]

    # Selección
    bank: Any  # BankSelectionResult
    charger: Any  # ChargerSelectionResult

    # Para UI / persistencia normalizada
    ah_commercial_str: str
    i_charger_commercial_str: str

    # Mensajes no bloqueantes
    warnings: List[str]



def _num_to_str_or_dash(x) -> str:
    if x is None:
        return "—"
    try:
        xf = float(x)
    except Exception:
        return "—"
    if xf <= 0:
        return "—"
    if xf.is_integer():
        return str(int(xf))
    return str(xf)


def run_bank_charger_engine(
    *,
    proyecto: Dict[str, Any],
    periods: List[Dict[str, Any]],
    rnd: Optional[Dict[str, Any]],
    kt_store: Dict[str, Any],
    i_perm: float,
    build_ieee485_fn,
    compute_bank_selection_fn,
    compute_charger_selection_fn,
) -> BankChargerBundle:
    warnings: List[str] = []

    # --- IEEE ---
    ieee = build_ieee485_fn(periods=periods, rnd=rnd, kt_store=kt_store)
    missing = list(getattr(ieee, "missing_kt_keys", []) or [])
    if missing:
        msg = "Faltan Kt en IEEE 485; selección incompleta hasta completar: "
        msg += ", ".join(missing[:10])
        if len(missing) > 10:
            msg += f" ... (+{len(missing)-10} más)"
        warnings.append(msg)

    # --- Factores banco ---
    k2 = to_float(proyecto.get("bb_k2_temp", 1.0), 1.0) or 1.0
    margen = to_float(proyecto.get("bb_margen_diseno", 1.15), 1.15) or 1.15
    enve = to_float(proyecto.get("bb_factor_envejec", 1.25), 1.25) or 1.25

    section_nets = getattr(ieee, "section_nets", []) or []
    rnd_net = float(getattr(ieee, "rnd_net", 0.0) or 0.0)

    bank = compute_bank_selection_fn(
        section_nets=section_nets,
        rnd_net=rnd_net,
        k2=k2,
        margen=margen,
        enve=enve,
        commercial_step_ah=to_float(proyecto.get("commercial_step_ah", 10.0), 10.0) or 10.0,
    )

    ah_com_str = _num_to_str_or_dash(getattr(bank, "ah_commercial", None))

    # --- Cargador ---
    t_rec_h = to_float(proyecto.get("charger_t_rec_h", 10.0), 10.0) or 10.0
    k_loss  = to_float(proyecto.get("charger_k_loss", 1.15), 1.15) or 1.15
    k_alt   = to_float(proyecto.get("charger_k_alt", 1.0), 1.0) or 1.0
    k_temp  = to_float(proyecto.get("charger_k_temp", 1.0), 1.0) or 1.0
    k_seg   = to_float(proyecto.get("charger_k_seg", 1.25), 1.25) or 1.25

    v_nom = to_float(proyecto.get("tension_nominal", 0.0), 0.0) or 0.0
    eff   = to_float(proyecto.get("charger_eff", 0.90), 0.90) or 0.90

    charger = compute_charger_selection_fn(
        ah_bank_commercial=getattr(bank, "ah_commercial", None),
        i_perm=float(i_perm or 0.0),
        t_rec_h=t_rec_h,
        k_loss=k_loss,
        k_alt=k_alt,
        k_temp=k_temp,
        k_seg=k_seg,
        v_nom=v_nom,
        eff=eff,
        commercial_step_a=to_float(proyecto.get("commercial_step_a", 10.0), 10.0) or 10.0,
        rounding_mode=(str(proyecto.get("charger_rounding_mode", "nearest"))).strip().lower(),
    )

    i_ch_com_str = _num_to_str_or_dash(getattr(charger, "i_commercial", None))

    return BankChargerBundle(
        ieee=ieee,
        missing_kt_keys=missing,
        bank=bank,
        charger=charger,
        ah_commercial_str=ah_com_str,
        i_charger_commercial_str=i_ch_com_str,
        warnings=warnings,
    )
