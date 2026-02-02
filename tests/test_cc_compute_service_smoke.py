# -*- coding: utf-8 -*-
"""Smoke test for CCComputeService (PyQt-free)."""

from services.compute.cc_compute_service import CCComputeService


def test_cc_compute_service_returns_totals():
    proj = {
        "tension_nominal": 125.0,
        "min_voltaje_cc": 10.0,
        "porcentaje_utilizacion": 50.0,
        "cc_usar_pct_global": True,
        "cc_num_escenarios": 2,
        "instalaciones": {
            "gabinetes": [
                {
                    "components": [
                        {
                            "id": "c1",
                            "data": {"tipo_consumo": "C.C. permanente", "potencia_w": 100},
                        },
                        {
                            "id": "c2",
                            "data": {
                                "tipo_consumo": "C.C. momentáneo",
                                "potencia_w": 50,
                                "cc_mom_incluir": True,
                                "cc_mom_escenario": 2,
                            },
                        },
                        {
                            "id": "c3",
                            "data": {
                                "tipo_consumo": "C.C. aleatorio",
                                "potencia_w": 30,
                                "cc_aleatorio_sel": True,
                            },
                        },
                    ]
                }
            ]
        },
    }

    res = CCComputeService().compute(proj)
    assert isinstance(res, dict)
    totals = res.get("totals") or {}
    assert totals.get("p_perm", 0.0) > 0.0
    assert totals.get("p_mom", 0.0) > 0.0
    assert totals.get("p_sel", 0.0) > 0.0
    by_scenario = res.get("by_scenario") or {}
    assert "1" in by_scenario
    assert "2" in by_scenario
