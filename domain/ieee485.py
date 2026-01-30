# domain/ieee485.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple

@dataclass(frozen=True)
class IEEE485Issue:
    level: str  # "error" | "warn"
    message: str

@dataclass(frozen=True)
class IEEE485Row:
    kind: str  # "section_header" | "data" | "subtot" | "total" | "random_header" | "random"
    # Valores display-ready (strings) + metadata
    period: str = ""
    load: str = ""
    change: str = ""
    duration: str = ""
    time_to_end: str = ""
    kt_key: Optional[str] = None
    kt_value: Any = ""
    pos: str = ""
    neg: str = ""
    header_text: str = ""

@dataclass(frozen=True)
class IEEE485Result:
    rows: List[IEEE485Row]
    section_nets: List[Optional[float]]  # net por sección (None si faltan Kt)
    rnd_net: float
    missing_kt_keys: List[str]
    issues: List[IEEE485Issue]


def _to_float_or_none(val) -> Optional[float]:
    if val in ("", None):
        return None
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return None


def missing_kt_report(periods: List[dict], kt_store: Dict[str, Any]) -> List[str]:
    n = len(periods)
    missing = []
    for s in range(1, n + 1):
        for i in range(1, s + 1):
            key = f"S{s}_P{i}"
            if _to_float_or_none(kt_store.get(key, "")) is None:
                missing.append(key)
    return missing


def build_ieee485(
    periods: List[dict],
    rnd: Optional[dict],
    kt_store: Dict[str, Any],
) -> IEEE485Result:
    issues: List[IEEE485Issue] = []
    if not periods:
        return IEEE485Result(rows=[], section_nets=[], rnd_net=0.0, missing_kt_keys=[], issues=[])

    A = [float(p["A"]) for p in periods]
    M = [float(p["M"]) for p in periods]
    n = len(A)

    def A_i(i: int) -> float:
        return 0.0 if i <= 0 else A[i - 1]

    def M_i(i: int) -> float:
        return M[i - 1]

    rows: List[IEEE485Row] = []
    section_nets: List[Optional[float]] = []

    for s in range(1, n + 1):
        if s < n:
            hdr = f"Sección {s} - Primero(s) {s} Periodos - Si A{s+1} es mayor que A{s}, ir a la sección {s+1}."
        else:
            hdr = f"Sección {s} - Primero(s) {s} Periodos."
        rows.append(IEEE485Row(kind="section_header", header_text=hdr))

        pos_sum = 0.0
        neg_sum = 0.0
        kt_missing = False

        for i in range(1, s + 1):
            Ai = A_i(i)
            dA = Ai - A_i(i - 1)
            Mi = M_i(i)
            T = sum(M[j - 1] for j in range(i, s + 1))

            key = f"S{s}_P{i}"
            kt_val = kt_store.get(key, "")
            kt = _to_float_or_none(kt_val)

            if kt is None:
                kt_missing = True

            # pos/neg se muestran vacíos si no hay Kt
            if kt is None:
                pos_s = ""
                neg_s = ""
            else:
                pos = (dA * kt) if dA > 0 else 0.0
                neg = (dA * kt) if dA < 0 else 0.0
                pos_s = f"{pos:.1f}"
                neg_s = f"{neg:.1f}"
                if dA > 0:
                    pos_sum += dA * kt
                elif dA < 0:
                    neg_sum += dA * kt

            rows.append(IEEE485Row(
                kind="data",
                period=str(i),
                load=f"A{i}={Ai:.0f}",
                change=f"A{i}−A{i-1}={dA:.0f}",
                duration=f"M{i}={Mi:.0f}",
                time_to_end=f"T= {'+'.join([f'M{j}' for j in range(i, s+1)])} = {T:.0f}",
                kt_key=key,
                kt_value=kt_val,
                pos=pos_s,
                neg=neg_s,
            ))

        # Sub Tot
        rows.append(IEEE485Row(
            kind="subtot",
            period="Sec",
            load=str(s),
            kt_key=f"S{s}_SUB",
            pos="" if kt_missing else f"{pos_sum:.1f}",
            neg="" if kt_missing else f"{neg_sum:.1f}",
        ))

        # Total (net)
        net = None if kt_missing else (pos_sum + neg_sum)
        section_nets.append(net)
        rows.append(IEEE485Row(
            kind="total",
            period="Total",
            pos="" if net is None else f"{net:.1f}",
            neg="***" if net is not None else "",
        ))

    # Random
    rnd_net = 0.0
    if rnd:
        rows.append(IEEE485Row(kind="random_header", header_text="Cargas Aleatorias (si es requerido)"))
        AR = float(rnd["A"])
        MR = float(rnd["M"])
        dAR = AR - 0.0

        kt_key = "R"
        kt_val = kt_store.get(kt_key, "")
        kt = _to_float_or_none(kt_val)
        if kt is None:
            pos_s = ""
            rnd_net = 0.0
        else:
            pos = dAR * kt
            pos_s = f"{pos:.1f}"
            rnd_net = pos  # net random

        rows.append(IEEE485Row(
            kind="random",
            period="A(al)",
            load=f"AR={AR:.0f}",
            change=f"AR−0={dAR:.0f}",
            duration=f"MR={MR:.0f}",
            time_to_end=f"T=MR = {MR:.0f}",
            kt_key=kt_key,
            kt_value=kt_val,
            pos=pos_s,
            neg="***" if pos_s else "",
        ))

    missing = missing_kt_report(periods, kt_store)
    if missing:
        issues.append(IEEE485Issue(level="warn", message=f"Faltan Kt: {len(missing)} celdas"))

    return IEEE485Result(
        rows=rows,
        section_nets=section_nets,
        rnd_net=rnd_net,
        missing_kt_keys=missing,
        issues=issues,
    )
