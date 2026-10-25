"""The results site's datasets: the whitelists of what a dataset may read, and every dataset (SQL) the site exports to data/<name>.json.

Split out of scripts/build_site.py without changing a line. A dataset may read ONLY a share_exec/share_club/share_privacy table, an approved
analyst aggregate, a whitelisted evaluation summary or governance metadata; `site_rules.check_dataset` enforces it. All data is SYNTHETIC.
"""
from __future__ import annotations

from scripts import site_p5_data as P5

SHARE_EXEC_PREFIX = "share_exec."
APPROVED_AGGREGATES = {"share_analyst.share_analyst__fan_event_study", "share_analyst.share_analyst__fan_acquisition_event_study"}
EVAL_WHITELIST = {
    "evaluation.eval_threshold_sweep", "evaluation.eval_pairwise", "evaluation.eval_clusters", "evaluation.eval_errors",
    "evaluation.eval_participation_accuracy", "evaluation.eval_retention", "evaluation.eval_fan_effect",
    "evaluation.eval_fan_matching_diagnostics", "evaluation.eval_headcount_overlap", "evaluation.eval_household_linkage",
    "evaluation.eval_acquisition", "evaluation.eval_acquisition_event_study",
}
GOVERNANCE_WHITELIST = {
    "quality.dq_contract_results", "reference.audience_column_policy", "reference.source_registry", "measurement.mart_restatement_log",
}
# Phase 5 (spec 12): share_club and share_privacy, aggregate quality marts, label-free uncertainty marts, whitelisted evaluation summaries (see scripts/site_phase5.py)
APPROVED_AGGREGATES |= P5.APPROVED
APPROVED_AGGREGATES |= {"phase6.mart_goal_scorecard", "phase6.mart_product_health", "phase6.mart_product_adoption"}
EVAL_WHITELIST |= P5.EVAL
GOVERNANCE_WHITELIST |= P5.GOVERNANCE
GOVERNANCE_WHITELIST |= {"reference.product_prioritization", "reference.product_targets", "reference.age_consent_rules", "reference.product_roadmap", "reference.roadmap_gap_links", "reference.dq_grade_bands"}

def _D(name, sql, relations, kind, title):
    return {"name": name, "sql": sql.strip(), "relations": set(relations), "kind": kind, "title": title}


DATASETS = [
    # ---- share_exec: what an executive audience may see ----
    _D("participation_bounds", "select * exclude (suppressed) from share_exec.share_exec__participation_bounds order by 1",
       ["share_exec.share_exec__participation_bounds"], "share_exec", "Unique participants with identity bounds"),
    _D("participation_by_country_latest", """
        select country_code, 'attributed (adds up)' as view, participants_attributed as participants from share_exec.share_exec__participation_by_country
        where participation_year = (select max(participation_year) from share_exec.share_exec__participation_by_country) and country_code is not null and participants_attributed is not null
        union all
        select country_code, 'present (overlaps)', participants_present from share_exec.share_exec__participation_by_country
        where participation_year = (select max(participation_year) from share_exec.share_exec__participation_by_country) and country_code is not null and participants_present is not null
        order by 1, 2""", ["share_exec.share_exec__participation_by_country"], "share_exec", "Participants by country, latest year"),
    _D("girls_share", """
        select participation_year, participants, girls_share_of_youth from share_exec.share_exec__participation_segments
        where country_code is null and age_band is null and girls_share_of_youth is not null order by 1""",
       ["share_exec.share_exec__participation_segments"], "share_exec", "Girls' share of youth participation"),
    _D("combined_reach", """
        select b.participation_year, b.identity_participants_point as participants, r.reported_headcount, r.combined_reach_low, r.combined_reach_high
        from share_exec.share_exec__participation_bounds b
        join share_exec.share_exec__reported_headcount r on r.participation_year = b.participation_year and r.country_code is null
        where r.reported_headcount is not null order by 1""",
       ["share_exec.share_exec__participation_bounds", "share_exec.share_exec__reported_headcount"], "share_exec", "Combined reach range"),
    _D("suppression_example", "select participation_year, sex, participants, suppressed from share_exec.share_exec__participation_by_sex "
       "order by participation_year, sex nulls first",
       ["share_exec.share_exec__participation_by_sex"], "share_exec", "Small-cell suppression: participants by sex, every year"),
    _D("retention_km_age", "select segment_value, years_since_entry, km_at_risk, km_survival, km_survival_ci_low, km_survival_ci_high "
       "from share_exec.share_exec__retention_survival where segment_type = 'entry_age_band' and km_survival is not null order by 1, 2",
       ["share_exec.share_exec__retention_survival"], "share_exec", "Retention curves by entry age band"),
    _D("retention_km_all", "select segment_value, years_since_entry, km_at_risk, km_survival, km_survival_ci_low, km_survival_ci_high "
       "from share_exec.share_exec__retention_survival where segment_type = 'ALL' and km_survival is not null order by 2",
       ["share_exec.share_exec__retention_survival"], "share_exec", "Retention curve, all entrants"),
    _D("retention_km_sex", "select segment_value, years_since_entry, km_at_risk, km_survival, km_survival_ci_low, km_survival_ci_high "
       "from share_exec.share_exec__retention_survival where segment_type = 'sex' and segment_value in ('F', 'M') and km_survival is not null order by 1, 2",
       ["share_exec.share_exec__retention_survival"], "share_exec", "Retention curves by sex"),
    _D("retention_cohorts", "select entry_year, years_since_entry, entry_cohort_size, cohort_retention_pct, cohort_retention_among_eligible_pct "
       "from share_exec.share_exec__retention_cohorts where cohort_retention_pct is not null order by 1, 2",
       ["share_exec.share_exec__retention_cohorts"], "share_exec", "Cohort triangle"),
    _D("fan_effect", "select estimator, fan_uplift_pct, fan_uplift_ci_low_pct, fan_uplift_ci_high_pct, fan_treated_households, caveat "
       "from share_exec.share_exec__fan_engagement_effect order by estimator",
       ["share_exec.share_exec__fan_engagement_effect"], "share_exec", "Fan engagement effect (estimates)"),
    _D("link_rate", "select coalesce(country_code, 'ALL') as country_code, program_households, linked_households, household_link_rate "
       "from share_exec.share_exec__household_link_rate where household_link_rate is not null order by country_code = 'ALL' desc, 1",
       ["share_exec.share_exec__household_link_rate"], "share_exec", "Household link rate by country"),
    # ---- approved aggregate (analyst share) ----
    _D("fan_event_study", """
        select months_since_event, 'participants' as group_name, fan_treated_mean_events as mean_events from share_analyst.share_analyst__fan_event_study where fan_treated_mean_events is not null
        union all
        select months_since_event, 'matched comparisons', fan_comparison_mean_events from share_analyst.share_analyst__fan_event_study where fan_comparison_mean_events is not null
        order by 2, 1""", ["share_analyst.share_analyst__fan_event_study"], "approved_aggregate", "Event study: mean events by month relative to first registration"),
    _D("fan_event_study_effect", "select months_since_event, fan_event_study_effect_pct as effect, fan_treated_households from share_analyst.share_analyst__fan_event_study "
       "where fan_event_study_effect_pct is not null order by 1",
       ["share_analyst.share_analyst__fan_event_study"], "approved_aggregate", "Event study: effect by month relative to first registration"),
    # ---- evaluation summaries (synthetic ground truth; labelled on every page that uses them) ----
    _D("threshold_sweep", """
        select threshold, 'precision' as measure, precision as value from evaluation.eval_threshold_sweep where matcher = 'fs'
        union all select threshold, 'recall', recall from evaluation.eval_threshold_sweep where matcher = 'fs' order by 2, 1""",
       ["evaluation.eval_threshold_sweep"], "evaluation", "Threshold sweep: precision and recall of the final matcher"),
    _D("sibling_merges_by_threshold", "select threshold, sibling_or_twin_false_merges, review_items_if_review from evaluation.eval_threshold_sweep where matcher = 'fs' order by 1",
       ["evaluation.eval_threshold_sweep"], "evaluation", "Sibling and twin false merges by threshold"),
    _D("matcher_comparison", """
        select p.matcher, p.scope, p.precision, p.recall, p.f1, c.sibling_or_twin_false_merges as sibling_twin_merges,
               c.predicted_participants, c.true_participants
        from evaluation.eval_pairwise p join evaluation.eval_clusters c using (matcher, stage, scope)
        where p.stage = 'PRE_REVIEW' order by p.matcher desc, p.scope""",
       ["evaluation.eval_pairwise", "evaluation.eval_clusters"], "evaluation", "Rules vs probabilistic matcher (before any steward review)"),
    _D("error_categories", "select matcher, error_type, likely_cause, count(*) as pairs from evaluation.eval_errors where stage = 'PRE_REVIEW' group by all order by 1, 2, 3",
       ["evaluation.eval_errors"], "evaluation", "Error categories at the automatic scope"),
    _D("identity_truth_check", "select participation_year, true_participants, participants_low, participants_point, participants_high, truth_within_range "
       "from evaluation.eval_participation_accuracy where grain = 'GLOBAL' order by 1",
       ["evaluation.eval_participation_accuracy"], "evaluation", "Identity bounds vs the synthetic truth"),
    _D("retention_vs_truth", """
        select years_since_entry, 'true (generator parameters)' as curve, true_survival as survival from evaluation.eval_retention where segment_type = 'entry_age_band' and segment_value = '14-17'
        union all select years_since_entry, 'Kaplan-Meier (age-outs censored)', km_survival from evaluation.eval_retention where segment_type = 'entry_age_band' and segment_value = '14-17'
        union all select years_since_entry, 'naive (age-out counted as churn)', naive_survival from evaluation.eval_retention where segment_type = 'entry_age_band' and segment_value = '14-17'
        order by 2, 1""", ["evaluation.eval_retention"], "evaluation", "Retention of entrants aged 14 to 17: truth, censored and naive"),
    _D("retention_vs_truth_all", """
        select years_since_entry, 'true (generator parameters)' as curve, true_survival as survival from evaluation.eval_retention where segment_type = 'ALL'
        union all select years_since_entry, 'Kaplan-Meier', km_survival from evaluation.eval_retention where segment_type = 'ALL'
        union all select years_since_entry, 'naive (age-out counted as churn)', naive_survival from evaluation.eval_retention where segment_type = 'ALL'
        order by 2, 1""", ["evaluation.eval_retention"], "evaluation", "Retention of all entrants: truth, censored and naive"),
    _D("fan_vs_truth", "select estimator, estimate_pct, ci_low_pct, ci_high_pct, true_effect_pct, true_uplift_parameter, estimate_over_truth, truth_in_ci "
       "from evaluation.eval_fan_effect where estimator in ('NAIVE_EXISTING', 'NAIVE', 'DID_ADDITIVE') order by estimator",
       ["evaluation.eval_fan_effect"], "evaluation", "Fan effect: naive and matched estimates against the true uplift"),
    _D("fan_diagnostics", "select measure, round(value, 9) as value from evaluation.eval_fan_matching_diagnostics order by 1",
       ["evaluation.eval_fan_matching_diagnostics"], "evaluation", "Why the matched estimate is where it is"),
    _D("reach_vs_truth", "select participation_year, true_combined_reach, combined_reach_low, combined_reach_high, truth_inside_range, naive_sum from evaluation.eval_headcount_overlap order by 1",
       ["evaluation.eval_headcount_overlap"], "evaluation", "Combined reach range against the synthetic truth"),
    _D("household_linkage_vs_truth", "select measure, n, value from evaluation.eval_household_linkage where measure in ('precision', 'precision_EMAIL', 'precision_PHONE', 'recall', 'recall_linkable', 'link_rate_of_all_participant_households') order by 1",
       ["evaluation.eval_household_linkage"], "evaluation", "Household linkage precision and recall"),
    # ---- fan acquisition, value and audience (share_exec) ----
    _D("fan_status_mix", """
        select fan_status, funnel_households as households from share_exec.share_exec__fan_funnel
        where segment is null and fan_status is not null and funnel_households is not null
          and cohort_year = (select max(cohort_year) from share_exec.share_exec__fan_funnel) order by households desc""",
       ["share_exec.share_exec__fan_funnel"], "share_exec", "Fan status of the latest cohort's registered households"),
    _D("funnel_rates", """
        select fan_status, 'Contactable (of linked)' as stage, funnel_contactable_rate as rate from share_exec.share_exec__fan_funnel
        where segment is null and fan_status is not null and fan_status <> 'UNLINKED' and funnel_contactable_rate is not null
          and cohort_year = (select max(cohort_year) from share_exec.share_exec__fan_funnel)
        union all
        select fan_status, 'Active (of linked)', funnel_active_rate from share_exec.share_exec__fan_funnel
        where segment is null and fan_status is not null and fan_status <> 'UNLINKED' and funnel_active_rate is not null
          and cohort_year = (select max(cohort_year) from share_exec.share_exec__fan_funnel)
        union all
        select fan_status, 'Monetized (of active)', funnel_monetized_rate from share_exec.share_exec__fan_funnel
        where segment is null and fan_status is not null and fan_status <> 'UNLINKED' and funnel_monetized_rate is not null
          and cohort_year = (select max(cohort_year) from share_exec.share_exec__fan_funnel)
        order by 2, 1""", ["share_exec.share_exec__fan_funnel"], "share_exec", "Funnel step rates by fan status, latest cohort"),
    _D("fan_rfm_latest", """
        select fan_group, segment, rfm_share from share_exec.share_exec__fan_rfm
        where rfm_share is not null and year = (select max(year) from share_exec.share_exec__fan_rfm) order by 1, 2""",
       ["share_exec.share_exec__fan_rfm"], "share_exec", "RFM segment mix by fan group, latest year"),
    _D("fan_survival", "select fan_group, months_since_origin, survival_at_risk, fan_survival, fan_survival_ci_low, fan_survival_ci_high from share_exec.share_exec__fan_survival "
       "where fan_survival is not null order by 1, 2", ["share_exec.share_exec__fan_survival"], "share_exec", "Fan account survival (Kaplan-Meier)"),
    _D("fan_ltv", "select fan_group, value_accounts, fan_ltv, fan_ltv_low, fan_ltv_high, horizon_months, currency_label from share_exec.share_exec__fan_value "
       "where fan_ltv is not null order by 1", ["share_exec.share_exec__fan_value"], "share_exec", "Modelled lifetime value per fan account (synthetic currency)"),
    _D("uplift_events", "select uplift_status_group, uplift_households, uplift_per_month, uplift_ci_low_per_month, uplift_ci_high_per_month from share_exec.share_exec__fan_value_uplift "
       "where uplift_outcome = 'events' and uplift_per_month is not null order by 1", ["share_exec.share_exec__fan_value_uplift"], "share_exec", "Value uplift: events per household-month"),
    _D("uplift_spend", "select uplift_status_group, uplift_households, uplift_per_month, uplift_ci_low_per_month, uplift_ci_high_per_month from share_exec.share_exec__fan_value_uplift "
       "where uplift_outcome = 'net_spend_total' and uplift_per_month is not null order by 1", ["share_exec.share_exec__fan_value_uplift"], "share_exec", "Value uplift: net spend per household-month (synthetic currency)"),
    _D("audience_series", """
        select month, 'Registered households' as measure, audience_registered as households from share_exec.share_exec__addressable_audience where household_group is null and audience_registered is not null
        union all select month, 'Linked to a fan account', audience_linked from share_exec.share_exec__addressable_audience where household_group is null and audience_linked is not null
        union all select month, 'Contactable (guardian opted in)', audience_contactable from share_exec.share_exec__addressable_audience where household_group is null and audience_contactable is not null
        union all select month, 'Active', audience_active from share_exec.share_exec__addressable_audience where household_group is null and audience_active is not null
        union all select month, 'Consent gap (active, no opt-in)', consent_gap_households from share_exec.share_exec__addressable_audience where household_group is null and consent_gap_households is not null
        order by 2, 1""", ["share_exec.share_exec__addressable_audience"], "share_exec", "Addressable audience and consent gap over time"),
    _D("audience_latest", """
        select coalesce(household_group, 'ALL') as household_group, audience_registered, audience_linked, audience_contactable, audience_contactable_email, audience_contactable_sms,
               audience_contactable_push, audience_active, consent_gap_households, consent_gap_share_of_active, consent_gap_value
        from share_exec.share_exec__addressable_audience
        where month = (select max(month) from share_exec.share_exec__addressable_audience) order by household_group nulls first""",
       ["share_exec.share_exec__addressable_audience"], "share_exec", "Audience and consent gap by household group, latest month (value in synthetic currency)"),
    _D("drive_stages", """
        with a as (select * from share_exec.share_exec__addressable_audience
                   where household_group is null and month = (select max(month) from share_exec.share_exec__addressable_audience))
        select 1 as step, 'Registered' as stage, audience_registered as households, 1.0 as conversion, 'registered households' as conversion_base from a
        union all select 2, 'Linked to a fan account', audience_linked, audience_linked * 1.0 / audience_registered, 'registered households' from a
        union all select 3, 'Contactable', audience_contactable, audience_contactable * 1.0 / audience_linked, 'linked households' from a
        union all select 4, 'Active', audience_active, audience_active * 1.0 / audience_linked, 'linked households' from a
        union all select 5, 'Unlinked (fan status unknown)', audience_registered - audience_linked, (audience_registered - audience_linked) * 1.0 / audience_registered, 'registered households' from a
        order by 1""", ["share_exec.share_exec__addressable_audience"], "share_exec", "Drive chart: households at each stage, latest month"),
    _D("consent_by_capture_point", "select consent_dimension_value as capture_point, consent_channel as channel, consent_lines, consent_opt_in_rate from share_exec.share_exec__consent_capture "
       "where consent_cut = 'BY_CAPTURE_POINT' and consent_opt_in_rate is not null order by 1, 2", ["share_exec.share_exec__consent_capture"], "share_exec", "Opt-in rate by capture point and channel"),
    _D("market_scatter", "select market_name, quadrant, participant_households, participation_per_1000, fan_accounts_per_1000 from share_exec.share_exec__market_quadrants "
       "where market_id is not null and participation_per_1000 is not null order by 1", ["share_exec.share_exec__market_quadrants"], "share_exec", "Markets: participation and fan accounts per 1,000 households"),
    _D("quadrant_counts", "select quadrant, count(*) filter (where market_id is not null) as markets_shown, sum(markets_in_row) as markets from share_exec.share_exec__market_quadrants "
       "group by quadrant order by quadrant", ["share_exec.share_exec__market_quadrants"], "share_exec", "Markets per quadrant (small markets are rolled up, not shown)"),
    # ---- evaluation summaries: acquisition (synthetic truth) ----
    _D("acq_estimates", """
        select case measure when 'incremental_accounts' then '1 Incremental (estimated)' when 'naive_net_new_scaled_by_link_rate' then '2 Naive: net-new, scaled by link rate'
                            else '3 Naive: net-new, linked only' end as method,
               estimate, ci_low, ci_high, truth as true_incremental_accounts
        from evaluation.eval_acquisition where measure in ('incremental_accounts', 'naive_net_new_scaled_by_link_rate', 'naive_net_new_observed') order by 1""",
       ["evaluation.eval_acquisition"], "evaluation", "Fan accounts the programme added: incremental vs naive vs the synthetic truth"),
    _D("acq_headline", "select incremental_fan_accounts, incremental_fan_accounts_ci_low, incremental_fan_accounts_ci_high, participant_households_compared, incremental_fan_accounts_per_100_households, "
       "incremental_fan_accounts_per_100_households_ci_low, incremental_fan_accounts_per_100_households_ci_high from share_exec.share_exec__acquisition_incrementality",
       ["share_exec.share_exec__acquisition_incrementality"], "share_exec", "Fans created by flag: the count and the rate per 100 participant households"),
    _D("acq_event_study", "select years_since_launch, estimate, ci_low, ci_high, truth, truth_in_ci from evaluation.eval_acquisition_event_study order by 1",
       ["evaluation.eval_acquisition_event_study"], "evaluation", "Acquisition event study against the synthetic truth"),
    # ---- governance metadata ----
    _D("contract_status", """
        select source_system, coalesce(nullif(component, ''), '-') as component, any_value(contract_version) as contract_version,
               count(*) filter (where status = 'PASS') as pass, count(*) filter (where status = 'WARN') as warn, count(*) filter (where status = 'ERROR') as error
        from quality.dq_contract_results group by 1, 2 order by 1, 2""", ["quality.dq_contract_results"], "governance", "Data contract status per source"),
    _D("source_status", "select source_system, onboarding_status, description from reference.source_registry order by 1",
       ["reference.source_registry"], "governance", "Onboarding status per source"),
    _D("audience_matrix", """
        select audience, count(distinct model) filter (where model <> '*') as share_tables, count(*) filter (where allowed = 'Y') as columns_allowed,
               count(*) filter (where allowed = 'N') as columns_denied
        from reference.audience_column_policy group by 1 order by 1""", ["reference.audience_column_policy"], "governance", "Audience access matrix (summary)"),
    _D("restatement_log", "select likely_cause, count(*) as kpi_rows, count(distinct kpi_id) as kpis, count(*) filter (where restatement_required) as restatement_required "
       "from measurement.mart_restatement_log group by 1 order by 1", ["measurement.mart_restatement_log"], "governance", "Restatement log against the latest published snapshots"),
]

DATASETS += P5.DATASETS
DATASETS += [
    _D("product_prioritization", """
        select product_id, product_name, value_to_goals, feasibility_today, data_readiness, privacy_risk, value_to_goals + feasibility_today + data_readiness - privacy_risk as total,
               case when value_to_goals >= 4 and data_readiness <= 2 then 'High value, low readiness: sequenced, not deprioritized'
                    when rank() over (order by value_to_goals + feasibility_today + data_readiness - privacy_risk desc) <= 2 then 'Build first' else 'Next' end as reading, rationale, status
        from reference.product_prioritization order by total desc, product_id""", ["reference.product_prioritization"], "governance", "Priority of the five data products"),
    _D("product_targets", "select gate_id, product_id, release, kind, metric, comparison, threshold_value, unit, baseline_2025, status from reference.product_targets order by gate_id",
       ["reference.product_targets"], "governance", "Exit criteria and guardrails with their 2025 baselines"),
    _D("roadmap", """
        select r.product_id, r.horizon, case r.horizon when 'DELIVERED' then 1 when 'NOW' then 2 when 'NEXT' then 3 else 4 end as horizon_order, r.version, r.title, r.phase_ref, r.gate_id,
               r.decision_owner_role, r.decision_text, r.status as card_status,
               g.kind, g.definition, g.comparison, g.target, g.unit, g.baseline_2025, g.source_model, g.source_field, g.current_value, g.status as gate_status, g.status_text, g.value_text,
               g.bar_fill_pct, g.target_marker_pct, g.n_met, g.n_gates, g.blocking_gate_plain
        from reference.product_roadmap r left join share_exec.share_exec__roadmap_gates g using (gate_id) order by r.product_id, horizon_order, r.version""",
       ["reference.product_roadmap", "share_exec.share_exec__roadmap_gates"], "governance", "Roadmap cards with their release gates (values computed in SQL)"),
    _D("roadmap_gap_links", "select * from reference.roadmap_gap_links order by gap_id", ["reference.roadmap_gap_links"], "governance", "Gaps found and the roadmap cards they changed (evidence read from the exports)"),
    _D("dq_grade_bands", "select grade, min_score, plain_label from reference.dq_grade_bands order by min_score desc", ["reference.dq_grade_bands"], "governance", "Quality grade bands (a grade is the band with the highest minimum score at or below the score)"),
    _D("age_rules", "select jurisdiction, age_min, age_max, who_consents, allowed_purposes, prohibited_purposes, verified, project_policy from reference.age_consent_rules order by jurisdiction, age_min",
       ["reference.age_consent_rules"], "governance", "Age-tier consent rules (project policy; the anchor rows are verified, the rest unverified)"),
    _D("conv_tier", """
        select age_tier, case age_tier when 'U13' then 'Under 13' when '13_15' then '13 to 15' when '16_17' then '16 to 17' when 'ADULT' then '18 and over' else 'Age not known' end as tier_label,
               case age_tier when 'U13' then 1 when '13_15' then 2 when '16_17' then 3 when 'ADULT' then 4 else 5 end as tier_order,
               step_no, step, kind, case kind when 'ACTIVATION' then 'Activation (needs guardian consent)' else 'Analytics only' end as kind_text, tier_funnel_households,
               case when tier_funnel_households is null then 'fewer than 10' else format('{:,}', tier_funnel_households) end as households_text, share_of_registered, suppressed
        from share_privacy.share_privacy__conversion_funnel_by_tier order by tier_order, step_no""", ["share_privacy.share_privacy__conversion_funnel_by_tier"], "share_privacy",
       "Households by the age tier of the youngest child at each step of the conversion funnel"),
    _D("goal_scorecard", "select goal_id, kpi_id, kpi_label, segment, year, value, value_low, value_high, unit, product_id, trust_label, trust_value, trust_unit, status from phase6.mart_goal_scorecard where year = (select max(year) from phase6.mart_goal_scorecard) order by goal_id, kpi_id, segment nulls first",
       ["phase6.mart_goal_scorecard"], "approved_aggregate", "Goal scorecard: each goal's KPIs with the data-trust companion (latest year)"),
    _D("product_health", "select product_id, area, measure, value_text, value_num, status, note from phase6.mart_product_health where area not in ('cost', 'freshness') order by product_id, area, measure",
       ["phase6.mart_product_health"], "approved_aggregate", "Product health (inside): quality, contracts, pipeline, trust, privacy (build time and load age stay local: they read the clock, so they change on every build)"),
    _D("product_adoption", "select product_id, stage, definition, real_events, simulated_events, status from phase6.mart_product_adoption order by product_id, stage",
       ["phase6.mart_product_adoption"], "approved_aggregate", "Adoption (outside): instrumented, awaiting real users"),
]
