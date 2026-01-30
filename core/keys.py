# -*- coding: utf-8 -*-
"""Single source of truth for project dict keys.

Why:
- Avoid typos scattered across screens/controllers.
- Make schema evolution (migrations) safer.
- Keep UI code (screens) free from deep dict access.

These are *storage keys* in the persisted project JSON/SSAA file.
Keep them stable and migrate when needed.
"""

from __future__ import annotations


class ProjectKeys:
    # generic
    CALCULATED = "calculated"

    # CC consumption
    UTILIZATION_PCT_GLOBAL = "porcentaje_utilizacion"
    CC_USE_PCT_GLOBAL = "cc_usar_pct_global"
    CC_SCENARIOS = "cc_escenarios"
    CC_SCENARIOS_SUMMARY = "cc_scenarios_summary"

    CC_PERM_PCT_CUSTOM = "cc_perm_pct_custom"
    CC_MOM_INCLUDE = "cc_mom_incluir"
    CC_MOM_SCENARIO = "cc_mom_escenario"
    CC_RANDOM_SEL = "cc_aleatorio_sel"

    # SSAA designer
    SSAA_TOPOLOGY = "ssaa_topology"
    SSAA_TOPOLOGY_LAYERS = "ssaa_topology_layers"

    # validation
    VALIDATION_ISSUES = "validation_issues"
    VALIDATION_ISSUES_BY_SECTION = "validation_issues_by_section"
