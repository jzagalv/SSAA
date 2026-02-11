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


def _pick_commercial_ah(
    *,
    required_ah: float,
    available_ah: List[float],
) -> tuple[Optional[float], Optional[str]]:
    vals_set = set()
    for v in (available_ah or []):
        try:
            vf = float(v)
        except Exception:
            continue
        if vf > 0.0:
            vals_set.add(vf)
    vals = sorted(vals_set)
    if not vals:
        return None, None

    req = float(required_ah or 0.0)
    if req <= 0:
        return vals[0], None

    for cap in vals:
        if cap >= req:
            if abs(cap - req) <= 1e-9:
                return cap, None
            return cap, (
                f"No existe capacidad exacta para {req:.2f} Ah en materiales; "
                f"se seleccionó {cap:.2f} Ah."
            )

    max_cap = vals[-1]
    return max_cap, (
        f"Capacidad requerida ({req:.2f} Ah) supera máximo disponible "
        f"en materiales ({max_cap:.2f} Ah)."
    )


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
    available_battery_ah: Optional[List[float]] = None,
    selected_battery_ah: Optional[float] = None,
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

    ah_required = to_float(getattr(bank, "ah_required", None), 0.0) or 0.0
    ah_calc = to_float(getattr(bank, "ah_commercial", None), 0.0) or 0.0
    ah_for_use = ah_calc if ah_calc > 0 else None

    sel_ah = to_float(selected_battery_ah, 0.0) if selected_battery_ah is not None else None
    if sel_ah is not None and sel_ah > 0:
        ah_for_use = sel_ah
        if ah_required > 0 and sel_ah < ah_required:
            warnings.append(
                f"Batería seleccionada ({sel_ah:.2f} Ah) menor a capacidad requerida ({ah_required:.2f} Ah)."
            )
    else:
        picked_ah, pick_warn = _pick_commercial_ah(
            required_ah=ah_required,
            available_ah=list(available_battery_ah or []),
        )
        if picked_ah is not None:
            ah_for_use = picked_ah
        if pick_warn:
            warnings.append(pick_warn)

    ah_com_str = _num_to_str_or_dash(ah_for_use)

    # --- Cargador ---
    t_rec_h = to_float(proyecto.get("charger_t_rec_h", 10.0), 10.0) or 10.0
    k_loss  = to_float(proyecto.get("charger_k_loss", 1.15), 1.15) or 1.15
    k_alt   = to_float(proyecto.get("charger_k_alt", 1.0), 1.0) or 1.0
    k_temp  = to_float(proyecto.get("charger_k_temp", 1.0), 1.0) or 1.0
    k_seg   = to_float(proyecto.get("charger_k_seg", 1.25), 1.25) or 1.25

    v_nom = to_float(proyecto.get("tension_nominal", 0.0), 0.0) or 0.0
    eff   = to_float(proyecto.get("charger_eff", 0.90), 0.90) or 0.90

    charger = compute_charger_selection_fn(
        ah_bank_commercial=ah_for_use,
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
