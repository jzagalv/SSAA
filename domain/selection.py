# domain/selection.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import math

def round_commercial(value: float, step=10.0, mode="ceil") -> Optional[float]:
    try:
        v = float(value)
    except Exception:
        return None
    if v <= 0:
        return None

    step = float(step) if step else 10.0

    if mode == "ceil":
        return math.ceil(v / step) * step
    if mode == "floor":
        return math.floor(v / step) * step
    return round(v / step) * step



@dataclass(frozen=True)
class BankSelectionResult:
    base_ah: float
    critical_section: Optional[int]
    k2: float
    margen: float
    enve: float
    factor_total: float
    ah_required: float
    ah_commercial: Optional[float]


@dataclass(frozen=True)
class ChargerSelectionResult:
    i_perm: float
    t_rec_h: float
    k_loss: float
    k_alt: float
    k_temp: float
    k_seg: float
    i_calc: float
    i_commercial: Optional[float]
    v_nom: float
    eff: float
    p_cc_w: float
    p_ca_w: float


def compute_bank_selection(
    section_nets: list,
    rnd_net: float,
    k2: float,
    margen: float,
    enve: float,
    commercial_step_ah: float = 10.0,
) -> BankSelectionResult:
    nets_num = [n for n in section_nets if isinstance(n, (int, float))]
    max_section = max(nets_num) if nets_num else 0.0

    critical_s = None
    for idx, val in enumerate(section_nets, start=1):
        if isinstance(val, (int, float)) and abs(val - max_section) < 1e-9:
            critical_s = idx
            break

    base_ah = max_section + (rnd_net or 0.0)
    factor_total = float(k2) * float(margen) * float(enve)

    ah_required = base_ah * factor_total if base_ah > 0 else 0.0
    ah_com = round_commercial(ah_required, step=commercial_step_ah, mode="ceil") if ah_required > 0 else None

    return BankSelectionResult(
        base_ah=base_ah,
        critical_section=critical_s,
        k2=float(k2),
        margen=float(margen),
        enve=float(enve),
        factor_total=float(factor_total),
        ah_required=float(ah_required),
        ah_commercial=ah_com,
    )


def compute_charger_selection(
    ah_bank_commercial: Optional[float],
    i_perm: float,
    t_rec_h: float,
    k_loss: float,
    k_alt: float,
    k_temp: float,
    k_seg: float,
    v_nom: float,
    eff: float,
    commercial_step_a: float = 10.0,
    rounding_mode: str = "nearest",
) -> ChargerSelectionResult:
    ah_bank = float(ah_bank_commercial or 0.0)

    i_calc = 0.0
    if ah_bank > 0 and t_rec_h > 0:
        i_calc = (((ah_bank / t_rec_h) * k_loss) + i_perm) * k_alt * k_temp * k_seg

    mode = (rounding_mode or "nearest").strip().lower()
    if mode not in ("ceil", "nearest", "floor"):
        mode = "nearest"
    i_com = round_commercial(i_calc, step=commercial_step_a, mode=mode) if i_calc > 0 else None

    p_cc = (float(v_nom) * float(i_com)) if (v_nom > 0 and i_com is not None) else 0.0
    p_ca = (p_cc / float(eff)) if (p_cc > 0 and eff and eff > 0) else 0.0

    return ChargerSelectionResult(
        i_perm=float(i_perm),
        t_rec_h=float(t_rec_h),
        k_loss=float(k_loss),
        k_alt=float(k_alt),
        k_temp=float(k_temp),
        k_seg=float(k_seg),
        i_calc=float(i_calc),
        i_commercial=i_com,
        v_nom=float(v_nom),
        eff=float(eff),
        p_cc_w=float(p_cc),
        p_ca_w=float(p_ca),
    )
