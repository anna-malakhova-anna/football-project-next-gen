# Data product changelog

One entry per product version. A version bump follows the rule in `docs/product/README.md`: **major** = a breaking change to an output port (a column removed or renamed) or a methodology change that restates numbers; **minor** = a new column or segment; **patch** = a fix with no interface change. Where numbers changed, the entry links the methodology CHANGELOG (`docs/methodology/CHANGELOG.md`). Synthetic project.

## 2026-10-18

| Product | Version | Change | Links | Detail for analysts |
|---|---|---|---|---|
| DP1 League Registration Intake | **1.0.0** | First versioned release (status MVP). Two new summary outputs: a scorecard and a fix list for each league, with no field about a person. | ADR-018, ADR-021 | New aggregate output ports `share_ops__league_scorecard` and `share_ops__league_fix_list` (per league, no person-level field). |
| DP2 Flag Participant & Household Master | **0.9.0** | Proposed. The participant, registration and review-queue tables for operations become named outputs. IDs can still change when records merge, so they stay internal. | ADR-003, ADR-004 | Formalizes the participant, registration and review-queue ops shares as ports. IDs can still change on a merge (ADR-004), so internal only. |
| DP3 Global Participation Insights | **0.9.0** | Proposed. Named outputs on the existing executive tables for participation. | ADR-015 | Ports on the existing exec shares for participation. |
| DP4 US Flag Growth & Club Market Insights | **1.0.0** | First versioned release (status MVP): the club outputs. Since Phase 5.1, a league counts in one market, in whole numbers, instead of being split by weight. How players are allocated is unchanged. No column removed. | ADR-016, ADR-020 | The club share ports. Leagues count in one market (whole numbers) instead of being split by weight; participant allocation is unchanged. |
| DP5 Flag-to-Fan Conversion Insights | **0.1.0** | Proposed (analytics only). The matched engagement lift is the one headline number. "Fans created by flag" gains a version per 100 households. A simple before-and-after estimate now sits beside the matched one. A new output shows the conversion steps by age group. | ADR-021, ADR-022 | `fan_uplift_pct` (matched) is the canonical engagement-lift metric; `incremental_fan_accounts` (renamed "Fans created by flag") gains a per-100-households version; new estimator `NAIVE_EXISTING` beside the matched estimate; new port `share_privacy__conversion_funnel_by_tier`. |

Methodology version stays **2.0**: no counting rule and no published KPI changed.
