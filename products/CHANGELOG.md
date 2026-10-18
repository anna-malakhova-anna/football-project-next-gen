# Data product changelog

One entry per product version. A version bump follows the rule in `docs/product/README.md`: **major** = a breaking change to an output port (a column removed or renamed) or a methodology change that restates numbers; **minor** = a new column or segment; **patch** = a fix with no interface change. Where numbers changed, the entry links the methodology CHANGELOG (`docs/methodology/CHANGELOG.md`). Synthetic project.

## 2026-10-18

| Product | Version | Change | Links |
|---|---|---|---|
| DP1 League Registration Intake | **1.0.0** | First versioned release (status MVP). New aggregate output ports `share_ops__league_scorecard` and `share_ops__league_fix_list` (per league, no person-level field). | ADR-018, ADR-021 |
| DP2 Flag Participant & Household Master | **0.9.0** | Proposed; formalizes the participant, registration and review-queue ops shares as ports. IDs can still change on a merge (ADR-004), so internal only. | ADR-003, ADR-004 |
| DP3 Global Participation Insights | **0.9.0** | Proposed; ports on the existing exec shares for participation. | ADR-015 |
| DP4 US Flag Growth & Club Market Insights | **1.0.0** | First versioned release (status MVP): the club share ports. Since Phase 5.1, leagues count in one market (whole numbers) instead of being split by weight; participant allocation is unchanged. No column removed. | ADR-016, ADR-020 |
| DP5 Flag-to-Fan Conversion Insights | **0.1.0** | Proposed (analytics only). `fan_uplift_pct` (matched) is the canonical engagement-lift metric; `incremental_fan_accounts` (renamed "Fans created by flag") gains a per-100-households version; new estimator `NAIVE_EXISTING` beside the matched estimate; new port `share_privacy__conversion_funnel_by_tier`. | ADR-021, ADR-022 |

Methodology version stays **2.0**: no counting rule and no published KPI changed.
