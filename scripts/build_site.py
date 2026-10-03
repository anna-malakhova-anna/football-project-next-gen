"""Build the static results site (site/) from the warehouse. All data is SYNTHETIC.

  uv run python -m scripts.build_site            (make site)

Rules the build enforces (and tests/test_build_site.py checks):
  * Every number on the site comes from a dataset in the DATASETS list below, exported to site/data/<name>.json. A dataset may read ONLY
      - a `share_exec` table (the executive share: aggregates, small cells suppressed),
      - an approved analyst aggregate (APPROVED_AGGREGATES: the event studies; nothing household-level),
      - a whitelisted evaluation summary (EVAL_WHITELIST: the synthetic ground truth, always labelled as such on the page), or
      - governance metadata (GOVERNANCE_WHITELIST: contract results, the access policy, the source registry, the restatement log).
    Anything else fails the build.
  * No number is computed in JavaScript. Every chart is a Vega-Lite spec that only maps fields to marks: transforms that calculate, aggregate, bin,
    fold or window are forbidden and the build fails on them. Rates, intervals and shares are computed in SQL, in the models.
  * Every chart has a one-sentence "what this shows" and a one-sentence "what it doesn't show", and a plain table of its numbers under it.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import shutil
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "warehouse" / "flag.duckdb"
OUT = ROOT / "site"

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
FORBIDDEN_TRANSFORMS = {"calculate", "aggregate", "joinaggregate", "window", "bin", "fold", "pivot", "regression", "loess", "density", "timeUnit", "stack"}
LIBS = ["https://cdn.jsdelivr.net/npm/vega@5", "https://cdn.jsdelivr.net/npm/vega-lite@5", "https://cdn.jsdelivr.net/npm/vega-embed@6"]


# ------------------------------------------------------------------ datasets
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
       "where participation_year = (select max(participation_year) from share_exec.share_exec__participation_by_sex) order by sex nulls first",
       ["share_exec.share_exec__participation_by_sex"], "share_exec", "Small-cell suppression example"),
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
       "from evaluation.eval_fan_effect where estimator in ('NAIVE', 'DID_ADDITIVE') order by estimator",
       ["evaluation.eval_fan_effect"], "evaluation", "Fan effect: naive and matched estimates against the true uplift"),
    _D("fan_diagnostics", "select measure, value from evaluation.eval_fan_matching_diagnostics order by 1",
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
        select fan_status, '2 Contactable (of linked)' as stage, funnel_contactable_rate as rate from share_exec.share_exec__fan_funnel
        where segment is null and fan_status is not null and fan_status <> 'UNLINKED' and funnel_contactable_rate is not null
          and cohort_year = (select max(cohort_year) from share_exec.share_exec__fan_funnel)
        union all
        select fan_status, '1 Active (of linked)', funnel_active_rate from share_exec.share_exec__fan_funnel
        where segment is null and fan_status is not null and fan_status <> 'UNLINKED' and funnel_active_rate is not null
          and cohort_year = (select max(cohort_year) from share_exec.share_exec__fan_funnel)
        union all
        select fan_status, '3 Monetized (of active)', funnel_monetized_rate from share_exec.share_exec__fan_funnel
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


# ------------------------------------------------------------------ checks
def check_dataset(ds: dict) -> list[str]:
    problems = []
    for rel in ds["relations"]:
        ok = (rel.startswith(SHARE_EXEC_PREFIX) or rel in APPROVED_AGGREGATES or rel in EVAL_WHITELIST or rel in GOVERNANCE_WHITELIST)
        if not ok:
            problems.append(f"dataset {ds['name']} reads {rel}: not share_exec, an approved aggregate, a whitelisted evaluation summary or governance metadata")
    sql = ds["sql"].lower()
    import re
    for found in set(re.findall(r"\b(?:from|join)\s+([a-z_]+\.[a-z_0-9]+)", sql)):
        if found not in {r.lower() for r in ds["relations"]}:
            problems.append(f"dataset {ds['name']}: SQL reads {found}, which is not declared in its relations")
    return problems


def check_spec(spec: dict, known: set[str], chart: str) -> list[str]:
    """A chart spec may only map fields to marks, from a registered dataset file. Walks the whole spec, layers included."""
    problems: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            if "data" in node and isinstance(node["data"], dict):
                url = node["data"].get("url")
                if url is None and "values" not in node["data"]:
                    problems.append(f"{chart}: a data block has no url")
                elif url is not None and url not in known:
                    problems.append(f"{chart}: data url {url} is not a registered dataset file")
                if "values" in node["data"]:
                    problems.append(f"{chart}: inline data values are not allowed (every number comes from a registered dataset)")
            for t in node.get("transform", []) or []:
                bad = FORBIDDEN_TRANSFORMS & set(t)
                if bad:
                    problems.append(f"{chart}: transform {sorted(bad)} computes numbers in the browser")
            for enc in (node.get("encoding") or {}).values():
                if isinstance(enc, dict):
                    bad = FORBIDDEN_TRANSFORMS & set(enc)
                    if bad:
                        problems.append(f"{chart}: encoding uses {sorted(bad)}, which computes numbers in the browser")
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(spec)
    return problems


# ------------------------------------------------------------------ charts
def _src(name: str) -> dict:
    return {"url": f"data/{name}.json", "format": {"type": "json", "property": "rows"}}


def _ax(title):
    return {"title": title}


def line_band(dataset, x, lo, hi, y, color=None, xt="", yt="", pct=True, y_min=0, y_max=None):
    enc_c = {"color": {"field": color, "type": "nominal", "title": None}} if color else {}
    scale = {"domain": [y_min, y_max]} if y_max is not None else {"zero": y_min == 0}
    fmt = {"format": "%"} if pct else {}
    return {"data": _src(dataset), "width": "container", "height": 300, "layer": [
        {"mark": {"type": "area", "opacity": 0.18}, "encoding": {"x": {"field": x, "type": "quantitative", "axis": _ax(xt)},
         "y": {"field": lo, "type": "quantitative", "scale": scale, "axis": {"title": yt, **fmt}}, "y2": {"field": hi}, **enc_c}},
        {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": x, "type": "quantitative"},
         "y": {"field": y, "type": "quantitative", "scale": scale}, **enc_c}},
    ]}


def charts():
    """-> {id: dict(page, title, spec, shows, doesnt, datasets, table_columns)}"""
    C = {}
    C["participation_trend"] = dict(
        page="participation", title="Unique participants, with identity bounds", datasets=["participation_bounds"],
        spec={"data": _src("participation_bounds"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "area", "opacity": 0.25}, "encoding": {"x": {"field": "participation_year", "type": "ordinal", "title": "Participation year"},
             "y": {"field": "identity_participants_low", "type": "quantitative", "scale": {"zero": False}, "title": "Unique participants"},
             "y2": {"field": "identity_participants_high"}}},
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "participation_year", "type": "ordinal"},
             "y": {"field": "identity_participants_point", "type": "quantitative"}}}]},
        shows="Registered participants per year (each person once), and the band that identity resolution alone could move the number by.",
        doesnt="Total flag football participation: only registered participants in onboarded sources, not informal play, attendance or missing sources. 2021 is the first data year.")
    C["country"] = dict(
        page="participation", title="Participants by country, latest year", datasets=["participation_by_country_latest"],
        spec={"data": _src("participation_by_country_latest"), "width": "container", "height": 300,
              "mark": "bar", "encoding": {"x": {"field": "country_code", "type": "nominal", "title": "Country"},
              "xOffset": {"field": "view", "type": "nominal"}, "y": {"field": "participants", "type": "quantitative", "title": "Participants"},
              "color": {"field": "view", "type": "nominal", "title": None}}},
        shows="Two views of the same people: attributed counts each person once, in the country of their latest registration, so it adds up; present counts a person in every country they played in.",
        doesnt="A global total: the present view must never be summed. Small countries are suppressed (blank) rather than shown with a tiny count.")
    C["girls"] = dict(
        page="participation", title="Girls' share of youth participation", datasets=["girls_share"],
        spec={"data": _src("girls_share"), "width": "container", "height": 260, "mark": {"type": "line", "point": True},
              "encoding": {"x": {"field": "participation_year", "type": "ordinal", "title": "Participation year"},
              "y": {"field": "girls_share_of_youth", "type": "quantitative", "axis": {"format": "%", "title": "Girls' share of youth"}, "scale": {"zero": False}}}},
        shows="The share of youth participants (17 or under) whose registration says female; a person with no recorded sex stays in the denominator.",
        doesnt="Why the share moves, or whether girls play as often as boys. It is registration-reported sex, not gender identity.")
    C["reach"] = dict(
        page="appendix", title="Combined reach: participants plus school and recreation program headcounts", datasets=["combined_reach"],
        spec={"data": _src("combined_reach"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "area", "opacity": 0.25, "color": "#d98a2b"}, "encoding": {"x": {"field": "participation_year", "type": "ordinal", "title": "Participation year"},
             "y": {"field": "combined_reach_low", "type": "quantitative", "scale": {"zero": False}, "title": "Children reached"}, "y2": {"field": "combined_reach_high"}}},
            {"mark": {"type": "line", "point": True, "color": "#2b6cb0"}, "encoding": {"x": {"field": "participation_year", "type": "ordinal"},
             "y": {"field": "reported_headcount", "type": "quantitative"}}}]},
        shows="The reported headcount from schools and recreation departments (line) and the range for participants plus that headcount (band): the low end assumes as much overlap as is possible, the high end none.",
        doesnt="A single combined number: aggregates cannot be matched to people, so some children are counted twice, and a PE unit is exposure, not participation. Programs are small cells and are suppressed where few.")
    C["threshold"] = dict(
        page="governance", title="Threshold sweep: precision and recall of the final matcher", datasets=["threshold_sweep"], evaluation=True,
        spec={"data": _src("threshold_sweep"), "width": "container", "height": 300, "mark": {"type": "line", "point": True},
              "encoding": {"x": {"field": "threshold", "type": "quantitative", "title": "Match probability threshold"},
              "y": {"field": "value", "type": "quantitative", "scale": {"domain": [0.9, 1.0]}, "title": "Pairwise precision / recall"},
              "color": {"field": "measure", "type": "nominal", "title": None}}},
        shows="How pairwise precision and recall move as the automatic-merge threshold changes, graded against the synthetic answer key.",
        doesnt="Performance on real data. The population is synthetic: phone numbers never change and one nickname list covers every nickname, so real data would score lower. The threshold was chosen once, before this chart.")
    C["siblings"] = dict(
        page="governance", title="Sibling and twin false merges by threshold", datasets=["sibling_merges_by_threshold"], evaluation=True,
        spec={"data": _src("sibling_merges_by_threshold"), "width": "container", "height": 240, "mark": {"type": "bar"},
              "encoding": {"x": {"field": "threshold", "type": "ordinal", "title": "Match probability threshold"},
              "y": {"field": "sibling_or_twin_false_merges", "type": "quantitative", "title": "Sibling / twin false merges"}}},
        shows="How many times two different children of the same household were merged into one person at each threshold.",
        doesnt="That a merge is harmless: a sibling merge is a privacy incident, which is why the final matcher guards against it and a steward reviews the probable pairs.")
    C["retention_km"] = dict(
        page="participation", title="Retention by entry age band (Kaplan-Meier, with 95% intervals)", datasets=["retention_km_age"],
        spec={"data": _src("retention_km_age"), "width": "container", "height": 320, "layer": [
            {"mark": {"type": "area", "opacity": 0.12}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative", "title": "Years since entry", "axis": {"tickMinStep": 1}},
             "y": {"field": "km_survival_ci_low", "type": "quantitative", "scale": {"domain": [0, 1]}, "axis": {"format": "%", "title": "Still registered"}},
             "y2": {"field": "km_survival_ci_high"}, "color": {"field": "segment_value", "type": "nominal", "title": "Entry age"}}},
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative"},
             "y": {"field": "km_survival", "type": "quantitative"}, "color": {"field": "segment_value", "type": "nominal"}}}]},
        shows="The share of each entry group still registered k years after their first season, treating a player who turns 18 or whose follow-up ends with the data as censored, not gone.",
        doesnt="Why players leave, or what the curves would be for adults continuing after 17 (this synthetic world has no adult continuation). Steps with fewer than 10 players at risk are not shown.")
    C["retention_sex"] = dict(
        page="participation", title="Retention by sex", datasets=["retention_km_sex"],
        spec={"data": _src("retention_km_sex"), "width": "container", "height": 260, "layer": [
            {"mark": {"type": "area", "opacity": 0.15}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative", "title": "Years since entry", "axis": {"tickMinStep": 1}},
             "y": {"field": "km_survival_ci_low", "type": "quantitative", "scale": {"domain": [0, 1]}, "axis": {"format": "%", "title": "Still registered"}},
             "y2": {"field": "km_survival_ci_high"}, "color": {"field": "segment_value", "type": "nominal", "title": "Sex"}}},
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative"},
             "y": {"field": "km_survival", "type": "quantitative"}, "color": {"field": "segment_value", "type": "nominal"}}}]},
        shows="The same retention curve for girls and boys, with intervals that overlap where the difference is within the noise.",
        doesnt="A causal difference. Segments overlap (age and division describe largely the same players) and nobody was assigned to them.")
    C["cohorts"] = dict(
        page="participation", title="Cohort triangle: share of each entry cohort still registered", datasets=["retention_cohorts"],
        spec={"data": _src("retention_cohorts"), "width": "container", "height": 220, "mark": "rect",
              "encoding": {"x": {"field": "years_since_entry", "type": "ordinal", "title": "Years since entry"},
              "y": {"field": "entry_year", "type": "ordinal", "title": "Entry cohort"},
              "color": {"field": "cohort_retention_pct", "type": "quantitative", "scale": {"domain": [0, 1], "scheme": "blues"}, "legend": {"format": "%", "title": "Still registered"}}}},
        shows="The classic triangle: for each entry year, the share of that cohort registered again 0, 1, 2, ... years later (only years that have happened).",
        doesnt="Retention corrected for ageing out: older youth fall off this view because they turn 18, not because they chose to leave. The table below has the corrected column.")
    C["naive_vs_censored"] = dict(
        page="participation", title="Entrants aged 14 to 17: naive vs censored vs the truth", datasets=["retention_vs_truth"], evaluation=True,
        spec={"data": _src("retention_vs_truth"), "width": "container", "height": 300, "mark": {"type": "line", "point": True},
              "encoding": {"x": {"field": "years_since_entry", "type": "quantitative", "title": "Years since entry", "axis": {"tickMinStep": 1}},
              "y": {"field": "survival", "type": "quantitative", "scale": {"domain": [0, 1]}, "axis": {"format": "%", "title": "Still registered"}},
              "color": {"field": "curve", "type": "nominal", "title": None, "legend": {"orient": "bottom", "columns": 1}}}},
        shows="Counting a 17-year-old who turns 18 as someone who quit makes retention look 22 to 24 points worse for this group; treating it as censored lands near the generator's true churn.",
        doesnt="A bias for younger entrants: they do not turn 18 inside the five-year window, so the naive and censored curves coincide for them. This is the reason the censoring rule exists.")
    C["fan_estimates"] = dict(
        page="value", title="Does registering a child raise a household's fan engagement? Naive vs matched vs truth", datasets=["fan_vs_truth"], evaluation=True,
        spec={"data": _src("fan_vs_truth"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "bar", "opacity": 0.8}, "encoding": {"x": {"field": "estimator", "type": "nominal", "title": None, "sort": ["NAIVE", "DID_ADDITIVE"]},
             "y": {"field": "estimate_pct", "type": "quantitative", "axis": {"format": "%", "title": "Change in events per household-month"}}}},
            {"mark": {"type": "rule", "strokeWidth": 2}, "encoding": {"x": {"field": "estimator", "type": "nominal", "sort": ["NAIVE", "DID_ADDITIVE"]},
             "y": {"field": "ci_low_pct", "type": "quantitative"}, "y2": {"field": "ci_high_pct"}}},
            {"mark": {"type": "tick", "color": "#c53030", "thickness": 3, "size": 70}, "encoding": {"x": {"field": "estimator", "type": "nominal", "sort": ["NAIVE", "DID_ADDITIVE"]},
             "y": {"field": "true_effect_pct", "type": "quantitative"}}}]},
        shows="The naive participant-vs-non-participant comparison (bar, left) against the matched before/after estimate (bar, right) and the true uplift the generator gave these households (red tick).",
        doesnt="A result for all participants. It covers households linked to a fan account (mostly North American) and is graded against synthetic truth; the matched estimate still sits above it, and its interval is somewhat too narrow (ADR-010).")
    C["event_study"] = dict(
        page="value", title="Event study: mean fan events per month around the first registration", datasets=["fan_event_study"],
        spec={"data": _src("fan_event_study"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "months_since_event", "type": "quantitative", "title": "Months since first registration"},
             "y": {"field": "mean_events", "type": "quantitative", "title": "Events per household-month"}, "color": {"field": "group_name", "type": "nominal", "title": None}}},
            {"mark": {"type": "rule", "strokeDash": [4, 4]}, "encoding": {"x": {"datum": 0, "type": "quantitative"}}}]},
        shows="Matched participants and matched comparisons track each other before registration (the flat pre period supports the design) and separate afterwards.",
        doesnt="A tight estimate: a small gap remains before registration (residual selection), and the pattern repeats with the NFL season. The vertical dashed line is month 0.")
    C["event_study_effect"] = dict(
        page="value", title="Event study: participants relative to comparisons, by month", datasets=["fan_event_study_effect"],
        spec={"data": _src("fan_event_study_effect"), "width": "container", "height": 260, "mark": {"type": "bar"},
              "encoding": {"x": {"field": "months_since_event", "type": "quantitative", "title": "Months since first registration"},
              "y": {"field": "effect", "type": "quantitative", "axis": {"format": "%", "title": "Participants vs comparisons"}}}},
        shows="The gap between the two lines above as a share of the comparison level: small and steady before month 0, about a fifth higher after.",
        doesnt="The matched estimate itself, which subtracts the pre-period gap (see the estimates chart). Read this as a check on the design, not as the answer.")

    # ---- fan acquisition ----
    ORDER = ["1 Incremental (estimated)", "2 Naive: net-new, scaled by link rate", "3 Naive: net-new, linked only"]
    C["acq_estimates"] = dict(
        page="acquisition", title="How many fan accounts did the programme add? Incremental vs naive vs the truth", datasets=["acq_estimates"], evaluation=True,
        spec={"data": _src("acq_estimates"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "bar", "opacity": 0.8}, "encoding": {"x": {"field": "method", "type": "nominal", "title": None, "sort": ORDER, "axis": {"labelAngle": 0, "labelLimit": 220}},
             "y": {"field": "estimate", "type": "quantitative", "title": "Fan accounts"}}},
            {"mark": {"type": "rule", "strokeWidth": 2}, "encoding": {"x": {"field": "method", "type": "nominal", "sort": ORDER}, "y": {"field": "ci_low", "type": "quantitative"}, "y2": {"field": "ci_high"}}},
            {"mark": {"type": "tick", "color": "#c53030", "thickness": 3, "size": 90}, "encoding": {"x": {"field": "method", "type": "nominal", "sort": ORDER}, "y": {"field": "true_incremental_accounts", "type": "quantitative"}}}]},
        shows="The estimate of accounts that exist because of the programme (left, with its interval) next to two naive counts of households that joined after registering, and the number the generator built in (red tick).",
        doesnt="A real programme's effect. Naive counts treat every new account of a registered household as caused by the programme (the scaled one assumes unlinked households behave like linked ones); the estimate compares launching markets with markets that had not launched yet, and is only as good as that comparison.")
    C["funnel_status"] = dict(
        page="acquisition", title="What fan status do registered households have?", datasets=["fan_status_mix"],
        spec={"data": _src("fan_status_mix"), "width": "container", "height": 280, "mark": "bar",
              "encoding": {"x": {"field": "households", "type": "quantitative", "title": "Registered households, latest cohort"}, "y": {"field": "fan_status", "type": "nominal", "sort": "-x", "title": None}}},
        shows="Every registered household of the latest cohort by fan status. UNLINKED (no fan account found) is the largest group and means unknown, not non-fan.",
        doesnt="How many unlinked households really are fans: some have an account the identity link could not find. Without identity resolution, multi-league kids would also inflate this household count.")
    C["funnel_rates"] = dict(
        page="acquisition", title="The funnel: from fan to active to contactable to paying", datasets=["funnel_rates"],
        spec={"data": _src("funnel_rates"), "width": "container", "height": 300, "mark": "bar",
              "encoding": {"x": {"field": "stage", "type": "nominal", "title": None, "axis": {"labelAngle": 0, "labelLimit": 200}}, "xOffset": {"field": "fan_status", "type": "nominal"},
              "y": {"field": "rate", "type": "quantitative", "axis": {"format": "%", "title": "Share of the previous step"}}, "color": {"field": "fan_status", "type": "nominal", "title": "Fan status"}}},
        shows="For linked households of the latest cohort, the share that are active, contactable and monetized, by fan status. Step 3 is a share of active households.",
        doesnt="Unlinked households (they have no account to be active or contactable) or causes: existing fans differ from net-new fans before they ever register a child.")
    C["acq_event_study"] = dict(
        page="acquisition", title="Event study: new accounts per 1,000 households, by years since a market launched", datasets=["acq_event_study"], evaluation=True,
        spec={"data": _src("acq_event_study"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "area", "opacity": 0.2}, "encoding": {"x": {"field": "years_since_launch", "type": "quantitative", "title": "Years since launch", "axis": {"tickMinStep": 1}},
             "y": {"field": "ci_low", "type": "quantitative", "title": "Extra new accounts per 1,000 households"}, "y2": {"field": "ci_high"}}},
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "years_since_launch", "type": "quantitative"}, "y": {"field": "estimate", "type": "quantitative"}}},
            {"mark": {"type": "tick", "color": "#c53030", "thickness": 3, "size": 18, "orient": "horizontal"}, "encoding": {"x": {"field": "years_since_launch", "type": "quantitative"}, "y": {"field": "truth", "type": "quantitative"}}}]},
        shows="The extra new accounts in launched markets compared with markets that had not launched yet, by year since launch, with intervals. A pre-launch value near zero supports the comparison; red ticks are the built-in truth.",
        doesnt="Anything about households: this is a market-level comparison, which is why it can say what the programme caused where the naive count cannot. Few markets stand behind some years, so the intervals are wide.")
    # ---- fan value and activeness ----
    C["rfm"] = dict(
        page="value", title="RFM segments by fan group, latest year", datasets=["fan_rfm_latest"],
        spec={"data": _src("fan_rfm_latest"), "width": "container", "height": 280, "mark": "bar",
              "encoding": {"x": {"field": "fan_group", "type": "nominal", "title": None, "axis": {"labelAngle": 0, "labelLimit": 200}}, "y": {"field": "rfm_share", "type": "quantitative", "axis": {"format": "%", "title": "Share of the group"}},
              "color": {"field": "segment", "type": "nominal", "title": "RFM segment"}}},
        shows="How each group's fan accounts split across recency, frequency and monetary segments (quintile-based, relative to that year).",
        doesnt="Absolute value: quintiles are relative, so every group has some Champions by construction. Read the mix between groups, not the labels alone.")
    C["fan_survival"] = dict(
        page="value", title="How long do fan accounts stay active? (Kaplan-Meier, 95% intervals)", datasets=["fan_survival"],
        spec={"data": _src("fan_survival"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "area", "opacity": 0.12}, "encoding": {"x": {"field": "months_since_origin", "type": "quantitative", "title": "Months since account origin"},
             "y": {"field": "fan_survival_ci_low", "type": "quantitative", "scale": {"domain": [0, 1]}, "axis": {"format": "%", "title": "Not lapsed"}}, "y2": {"field": "fan_survival_ci_high"},
             "color": {"field": "fan_group", "type": "nominal", "title": "Fan group"}}},
            {"mark": {"type": "line"}, "encoding": {"x": {"field": "months_since_origin", "type": "quantitative"}, "y": {"field": "fan_survival", "type": "quantitative"}, "color": {"field": "fan_group", "type": "nominal"}}}]},
        shows="The share of fan accounts that have not lapsed (a long gap in engagement) by months since the account began, with accounts still active at the end of the data treated as censored.",
        doesnt="Why accounts lapse. Groups are not randomly assigned, so differences between them mix who joins with what the programme does.")
    C["fan_ltv"] = dict(
        page="value", title="Modelled lifetime value per fan account (synthetic currency)", datasets=["fan_ltv"],
        spec={"data": _src("fan_ltv"), "width": "container", "height": 260, "layer": [
            {"mark": {"type": "bar", "opacity": 0.8}, "encoding": {"x": {"field": "fan_group", "type": "nominal", "title": None, "axis": {"labelAngle": 0, "labelLimit": 200}}, "y": {"field": "fan_ltv", "type": "quantitative", "title": "Value over the horizon, synthetic currency"}}},
            {"mark": {"type": "rule", "strokeWidth": 2}, "encoding": {"x": {"field": "fan_group", "type": "nominal"}, "y": {"field": "fan_ltv_low", "type": "quantitative"}, "y2": {"field": "fan_ltv_high"}}}]},
        shows="Expected net spend per account over the horizon (net spend per active month times expected active months), with a range.",
        doesnt="Revenue. It is an illustrative expectation in synthetic currency, from observed spend and lapse behaviour; the range reflects sampling, not the modelling assumptions.")
    C["uplift_events"] = dict(
        page="value", title="Existing fans: events per household-month after registering a child", datasets=["uplift_events"],
        spec={"data": _src("uplift_events"), "width": "container", "height": 240, "layer": [
            {"mark": {"type": "bar", "opacity": 0.8}, "encoding": {"x": {"field": "uplift_status_group", "type": "nominal", "title": "Status before registering", "axis": {"labelAngle": 0}}, "y": {"field": "uplift_per_month", "type": "quantitative", "title": "Extra events per household-month"}}},
            {"mark": {"type": "rule", "strokeWidth": 2}, "encoding": {"x": {"field": "uplift_status_group", "type": "nominal"}, "y": {"field": "uplift_ci_low_per_month", "type": "quantitative"}, "y2": {"field": "uplift_ci_high_per_month"}}}]},
        shows="The matched before/after change in fan events for households that already had an account (EXISTING), had lapsed (LAPSED) and all linked households, with intervals.",
        doesnt="A result for unlinked households, or a percentage for lapsed ones (their baseline is near zero, so the per-month difference is the honest measure).")
    C["uplift_spend"] = dict(
        page="value", title="Existing fans: net spend per household-month after registering a child (synthetic currency)", datasets=["uplift_spend"],
        spec={"data": _src("uplift_spend"), "width": "container", "height": 240, "layer": [
            {"mark": {"type": "bar", "opacity": 0.8}, "encoding": {"x": {"field": "uplift_status_group", "type": "nominal", "title": "Status before registering", "axis": {"labelAngle": 0}}, "y": {"field": "uplift_per_month", "type": "quantitative", "title": "Extra net spend per household-month"}}},
            {"mark": {"type": "rule", "strokeWidth": 2}, "encoding": {"x": {"field": "uplift_status_group", "type": "nominal"}, "y": {"field": "uplift_ci_low_per_month", "type": "quantitative"}, "y2": {"field": "uplift_ci_high_per_month"}}}]},
        shows="The matched before/after change in net spend, with intervals, by status before registering.",
        doesnt="Revenue: the currency is synthetic and refunds are netted. It is linked households only.")
    # ---- audience and consent ----
    C["audience"] = dict(
        page="audience", title="The addressable audience and the consent gap over time", datasets=["audience_series"],
        spec={"data": _src("audience_series"), "width": "container", "height": 320, "mark": {"type": "line"},
              "encoding": {"x": {"field": "month", "type": "temporal", "title": None}, "y": {"field": "households", "type": "quantitative", "title": "Households"},
              "color": {"field": "measure", "type": "nominal", "title": None, "legend": {"orient": "bottom", "columns": 2}}}},
        shows="Registered households, those linked to a fan account, those a guardian has opted in (contactable), those active, and the active households with no opt-in at all (the consent gap).",
        doesnt="A marketing list: these are counts, no household is identified here or anywhere an audience can see. A household with no consent record is not contactable, and no record is not a no.")
    C["consent_capture"] = dict(
        page="audience", title="Where is consent captured? Opt-in rate by capture point and channel", datasets=["consent_by_capture_point"],
        spec={"data": _src("consent_by_capture_point"), "width": "container", "height": 280, "mark": "bar",
              "encoding": {"x": {"field": "capture_point", "type": "nominal", "title": None, "axis": {"labelAngle": 0}}, "xOffset": {"field": "channel", "type": "nominal"},
              "y": {"field": "consent_opt_in_rate", "type": "quantitative", "axis": {"format": "%", "title": "Opt-in rate"}}, "color": {"field": "channel", "type": "nominal", "title": "Channel"}}},
        shows="Among accounts with a consent record at each capture point, the share that opted in, by channel.",
        doesnt="Consent among accounts with no record: they are not in the denominator and are never counted as a no (or a yes). Capture points differ in who is asked, so this is not a ranking of them.")
    C["market_quadrants"] = dict(
        page="audience", title="Markets: where flag football and the fan base are each strong (synthetic markets)", datasets=["market_scatter"],
        spec={"data": _src("market_scatter"), "width": "container", "height": 340, "mark": {"type": "point", "filled": True, "size": 80},
              "encoding": {"x": {"field": "participation_per_1000", "type": "quantitative", "title": "Participant households per 1,000 households"}, "y": {"field": "fan_accounts_per_1000", "type": "quantitative", "title": "Fan accounts per 1,000 households"},
              "color": {"field": "quadrant", "type": "nominal", "title": "Quadrant"}, "tooltip": [{"field": "market_name"}, {"field": "quadrant"}]}},
        shows="Each synthetic market with enough participant households, by participation and fan accounts per 1,000 households, coloured by quadrant (cut-offs are the medians).",
        doesnt="Real places: the markets are invented. Markets with too few participant households are rolled up and not drawn, and a quadrant says where to look, not what to do.")
    return C


# ------------------------------------------------------------------ pages
PAGES = [("index", "Overview"), ("acquisition", "Fan acquisition"), ("value", "Fan value & activeness"), ("audience", "Audience & consent"), ("participation", "Participation"), ("governance", "Data trust & governance")]
APPENDIX = [("appendix", "Appendix")]          # a stretch source (school and recreation headcounts): built, linked from the footer, not in the main navigation
CSS = """
:root{--bg:#fbfbf9;--fg:#1c1f24;--muted:#5b6470;--line:#dfe2e6;--card:#ffffff;--accent:#2b6cb0;--warn:#b7791f}
@media (prefers-color-scheme: dark){:root{--bg:#14171b;--fg:#e8eaed;--muted:#9aa4b0;--line:#2a2f36;--card:#1b1f24;--accent:#63a4e8;--warn:#e0a84a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
header{border-bottom:1px solid var(--line);background:var(--card)}nav{max-width:980px;margin:0 auto;padding:12px 16px;display:flex;gap:6px 18px;flex-wrap:wrap;align-items:center}
nav a{color:var(--muted);text-decoration:none;padding:4px 0;border-bottom:2px solid transparent}nav a.on{color:var(--fg);border-color:var(--accent)}nav strong{margin-right:auto}
main{max-width:980px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.8rem;margin:.2em 0 .4em}h2{font-size:1.25rem;margin:1.8em 0 .4em}
.banner{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--warn);padding:10px 14px;border-radius:6px;color:var(--muted);margin:14px 0}
.chart{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:18px 0}.chart h3{margin:0 0 8px;font-size:1.05rem}
.note{color:var(--muted);font-size:.93rem;margin:4px 0}.note b{color:var(--fg)}.tag{display:inline-block;font-size:.75rem;border:1px solid var(--warn);color:var(--warn);border-radius:99px;padding:0 8px;margin-left:8px;vertical-align:middle}
details{margin-top:8px}summary{cursor:pointer;color:var(--accent);font-size:.9rem}table{border-collapse:collapse;width:100%;font-size:.85rem;margin:8px 0;display:block;overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:4px 10px;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{color:var(--muted);font-weight:600}
.flow{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:14px 0}.flow span{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px 10px;font-size:.9rem}.flow i{color:var(--muted);font-style:normal}
ol.tour li{margin:6px 0}a{color:var(--accent)}code{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:0 4px;font-size:.88em}
footer{max-width:980px;margin:0 auto;padding:0 16px 40px;color:var(--muted);font-size:.85rem}
.vega-embed{width:100%}
"""
EMBED_JS = """
(function () {
  var specs = document.querySelectorAll('script[type="application/json"][data-chart]');
  specs.forEach(function (node) {
    var spec = JSON.parse(node.textContent);
    var target = document.getElementById(node.dataset.chart);
    if (window.vegaEmbed && target) { vegaEmbed(target, spec, {actions: false, renderer: 'svg'}); }
  });
})();
"""


def esc(v) -> str:
    return html.escape(str(v))


def fmt_cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.4f}" if abs(v) < 10 else f"{v:,.1f}"
    if isinstance(v, int):
        return f"{v:,}" if abs(v) >= 10000 else str(v)
    return str(v)


def table_html(ds: dict, limit: int = 60) -> str:
    cols, rows = ds["columns"], ds["rows"][:limit]
    if not rows:
        return f"<p class='note'><b>No rows.</b> The query returned nothing, which is the expected result when {esc(ds['title'].lower())} has nothing to report.</p>"
    head = "".join(f"<th>{esc(c)}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{esc(fmt_cell(r[c]))}</td>" for c in cols) + "</tr>" for r in rows)
    more = f"<p class='note'>First {limit} of {len(ds['rows'])} rows; the full file is data/{ds['name']}.json.</p>" if len(ds["rows"]) > limit else ""
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>{more}"


def chart_block(cid: str, ch: dict, data: dict) -> str:
    tag = '<span class="tag">synthetic truth, evaluation only</span>' if ch.get("evaluation") else ""
    tables = "".join(f"<p class='note'><b>{esc(data[n]['title'])}</b> <code>{esc(data[n]['source'])}</code></p>{table_html(data[n])}" for n in ch["datasets"])
    return (f'<section class="chart" id="sec-{cid}"><h3>{esc(ch["title"])}{tag}</h3><div id="{cid}" role="img" aria-label="{esc(ch["title"])}"></div>'
            f'<p class="note"><b>What this shows.</b> {esc(ch["shows"])}</p><p class="note"><b>What it does not show.</b> {esc(ch["doesnt"])}</p>'
            f'<details><summary>The numbers behind this chart</summary>{tables}</details>'
            f'<script type="application/json" data-chart="{cid}">{json.dumps(ch["spec"])}</script></section>')


def page(slug: str, title: str, body: str, built: str) -> str:
    nav = "".join(f'<a href="{"index" if s == "index" else s}.html" class="{"on" if s == slug else ""}">{esc(t)}</a>' for s, t in PAGES)
    appendix_link = '<a href="appendix.html">Appendix: school and recreation programs (a stretch source)</a>' 
    libs = "".join(f'<script src="{u}"></script>' for u in LIBS)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Counting Flag Football: {esc(title)}</title><style>{CSS}</style></head><body><header><nav><strong>Counting Flag Football</strong>{nav}</nav></header>'
            f'<main><div class="banner"><b>Synthetic data.</b> Every person on this site is generated. Numbers count registered participants in onboarded sources, '
            f'not total participation. Charts marked "synthetic truth" compare the pipeline with the generator\'s answer key, which no real project would have.</div>'
            f'{body}</main><footer>Built {built} by scripts/build_site.py from share_exec exports and whitelisted evaluation summaries. No number on this site is computed in the browser. {appendix_link}</footer>'
            f'{libs}<script>{EMBED_JS}</script></body></html>')


def kv(data: dict, name: str) -> dict:
    return {r["measure"]: r for r in data[name]["rows"]}


def build_pages(data: dict, chart_defs: dict, facts: dict) -> dict[str, tuple[str, str]]:
    built = {}
    blocks = {p: [] for p, _ in PAGES + APPENDIX}
    for cid, ch in chart_defs.items():
        blocks[ch["page"]].append(chart_block(cid, ch, data))

    flow = " <i>&rarr;</i> ".join(f"<span>{esc(s)}</span>" for s in ["sources", "contracts", "raw", "staging", "identity", "households", "fan models", "shares", "this site"])
    latest = facts["latest_year"]
    built["index"] = ("Overview", f"""
<h1>Counting flag football's fans</h1>
<p>Flag football registers children. This project asks a different question: <i>how many fans does that create, how engaged and valuable are they, and how many can we actually contact?</i>
It is a governed data platform built end to end on <b>synthetic</b> data (the real equivalent would be minors' personal data), and every claim is graded against the generator's answer key.</p>
<div class="flow">{flow}</div>
<p class="note">Five sources (a league CSV, a club API, a federation workbook, school headcounts and a fan feed) are contracted, loaded as-is, cleaned in SQL, resolved to people and households,
linked to fan accounts under a restricted-zone policy, shared by audience with small numbers suppressed, and published as versioned snapshots.</p>
<h2>Headline</h2>
<table><tbody>
<tr><td>Fan accounts the programme added (incremental estimate, with interval)</td><td>{fmt_cell(facts['incremental'])} ({fmt_cell(facts['inc_low'])} to {fmt_cell(facts['inc_high'])}); the naive count says {fmt_cell(facts['naive_scaled'])}</td></tr>
<tr><td>Addressable audience, {facts['audience_month']} (households a guardian has opted in)</td><td>{fmt_cell(facts['contactable'])} of {fmt_cell(facts['registered'])} registered households</td></tr>
<tr><td>Consent gap (active households with no opt-in)</td><td>{fmt_cell(facts['gap'])}, about {facts['gap_share']:.0%} of active households</td></tr>
<tr><td>Unique registered participants, {latest}</td><td>{fmt_cell(facts['participants'])} (identity range {fmt_cell(facts['low'])} to {fmt_cell(facts['high'])})</td></tr>
<tr><td>Matched fan-engagement uplift after a first registration (linked households)</td><td>{facts['did_pct']:+.1%} (naive says {facts['naive_pct']:+.1%}; truth {facts['truth_pct']:+.1%})</td></tr>
</tbody></table>
<h2>A five-minute tour</h2>
<ol class="tour">
<li><a href="acquisition.html">Fan acquisition</a>: how many fans flag football created, and why the naive count is too big.</li>
<li><a href="value.html">Fan value &amp; activeness</a>: who is engaged, how long fans stay, what a fan is worth, and what registering a child changes.</li>
<li><a href="audience.html">Audience &amp; consent</a>: how many fans can be contacted, where consent is captured, and the gap. Governance sets the size of the marketable audience.</li>
<li><a href="participation.html">Participation</a>: the original question, how many people play, and who stays.</li>
<li><a href="governance.html">Data trust &amp; governance</a>: identity resolution (why the household count is right), contracts, who sees what, what changed after publishing.</li>
</ol>
<p class="note">Decisions and their reasons are in the ADRs; the counting rules are in the methodology memos. Both are linked from <a href="governance.html">Data trust &amp; governance</a>.</p>""")
    built["acquisition"] = ("Fan acquisition", "<h1>Fan acquisition</h1><p class='note'>How many fans did the programme create? The first chart is the answer; the rest show where it comes from. Funnel and status describe households linked to a fan account; "
                            "identity resolution is why the denominator is right (a child in several leagues is one household member, not several).</p>" + "".join(blocks["acquisition"]))
    built["value"] = ("Fan value & activeness", "<h1>Fan value &amp; activeness</h1><p class='note'>Estimates describe households linked to a fan account, under a restricted-zone policy (ADR-009). Nothing household-level is shown; money is synthetic currency.</p>"
                      + "".join(blocks["value"]) + "<h2>Why the matched engagement estimate is where it is</h2>" + table_html(data["fan_diagnostics"]))
    built["audience"] = ("Audience & consent", "<h1>Audience &amp; consent</h1><p class='note'>Governance determines the size of the marketable audience: only a guardian's recorded opt-in makes a household contactable. "
                         "Counts only; nobody here is a list, and no linked household reaches marketing or media (ADR-009).</p>"
                         + "".join(blocks["audience"]) + "<h2>Latest month by household group</h2>" + table_html(data["audience_latest"])
                         + "<h2>Markets per quadrant</h2>" + table_html(data["quadrant_counts"])
                         + "<h2>Who can be linked</h2>" + table_html(data["link_rate"]))
    built["participation"] = ("Participation", "<h1>Participation</h1><p class='note'>The original question, condensed: how many people play, with the band that identity resolution leaves, and who stays. Retention is Kaplan-Meier from the first season, computed in SQL: "
                              "a player who turns 18, or whose follow-up ends with the data, is censored, not counted as gone.</p>" + "".join(blocks["participation"]))
    built["appendix"] = ("Appendix", "<h1>Appendix: school and recreation programs</h1><p class='note'>A <b>stretch</b> source: school districts and recreation departments report how many "
                         "children are in their programs. The counts have no people in them, so they are never added to participants.</p>" + "".join(blocks["appendix"])
                         + "<h2>Against the synthetic truth</h2>" + table_html(data["reach_vs_truth"]))
    built["governance"] = ("Data trust & governance", f"""<h1>Data trust &amp; governance</h1>
<h2>Identity: can the numbers be trusted?</h2>
<p class='note'>Matching people across sources is the hard part. The generator's answer key grades it; real projects have no key.</p>
{"".join(blocks["governance"])}
<h3>Rules vs probabilistic, before any steward review</h3>{table_html(data["matcher_comparison"])}
<p class="note"><b>What this shows.</b> A rules baseline, a literal Fellegi-Sunter matcher (fs_naive) and the corrected one (fs) on the same data. <b>What it does not show.</b> Real-world accuracy; the sibling and twin merges are the incidents that matter.</p>
<h3>Error categories</h3>{table_html(data["error_categories"])}
<h3>Identity bounds against the synthetic truth</h3>{table_html(data["identity_truth_check"])}
<h3>Household linkage precision and recall against the synthetic truth</h3>{table_html(data["household_linkage_vs_truth"])}
<h2>Who sees what</h2>{table_html(data['audience_matrix'])}
<p class="note"><b>What this shows.</b> Five audiences, each with a column-level allow list; the executive audience gets aggregates only, and nothing linked reaches marketing or media. <b>What it does not show.</b> Real access control: this is a policy enforced by a build check, not by a database role (ADR-006).</p>
<h2>Suppression example</h2>{table_html(data['suppression_example'])}
<p class="note"><b>What this shows.</b> A count below 10 is hidden (PRIMARY) and, where subtraction would reveal it, a second cell too (SECONDARY). <b>What it does not show.</b> Formal disclosure control; production would use sdcMicro or tau-Argus.</p>
<h2>Data contracts per source</h2>{table_html(data['contract_status'])}
<h2>Onboarding status</h2>{table_html(data['source_status'])}
<h2>What changed after publishing</h2>{table_html(data['restatement_log'])}
<p class="note">Worked examples: a steward decision, the window growing from three to five years, and a methodology bump that only adds KPIs, in <code>docs/reports/restatement_demo.md</code>.</p>
<h2>Documents</h2><ul>
<li><code>docs/methodology/counting-a-participant.md</code>: the counting rules C1 to C15</li>
<li><code>docs/methodology/flag-as-fan-acquisition.md</code>: fan status, why unlinked is not a non-fan, market-level acquisition, LTV assumptions (draft)</li>
<li><code>docs/decisions/</code>: ADR-001 to ADR-011, including the linkage governance decision (ADR-009), the fandom design (ADR-010) and the acquisition measurement design (ADR-011)</li>
<li><code>docs/playbook/onboard-a-source.md</code>: how a source is onboarded, with the logs for the two Phase 4 sources</li>
<li><code>docs/access_policy.md</code>, <code>docs/metrics.md</code>, <code>docs/data_dictionary.md</code></li></ul>""")
    return built


# ------------------------------------------------------------------ build
def export(con: duckdb.DuckDBPyConnection) -> dict:
    data = {}
    for ds in DATASETS:
        problems = check_dataset(ds)
        if problems:
            raise SystemExit("SITE BUILD REFUSED:\n  " + "\n  ".join(problems))
        cur = con.execute(ds["sql"])
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        data[ds["name"]] = {"name": ds["name"], "title": ds["title"], "source": ", ".join(sorted(ds["relations"])), "kind": ds["kind"], "columns": cols, "rows": rows}
    return data


def build(db: Path = DB, out: Path = OUT) -> dict:
    con = duckdb.connect(str(db), read_only=True)
    try:
        data = export(con)
        latest = con.execute("select max(participation_year) from share_exec.share_exec__participation_bounds").fetchone()[0]
    finally:
        con.close()
    chart_defs = charts()
    known = {f"data/{n}.json" for n in data}
    problems = [p for cid, ch in chart_defs.items() for p in check_spec(ch["spec"], known, cid)]
    for cid, ch in chart_defs.items():
        for n in ch["datasets"]:
            if n not in data:
                problems.append(f"{cid}: dataset {n} is not defined")
    if problems:
        raise SystemExit("SITE BUILD REFUSED:\n  " + "\n  ".join(problems))
    rows = lambda n: data[n]["rows"]  # noqa: E731
    bounds = next(r for r in rows("participation_bounds") if r["participation_year"] == latest)
    fan = {r["estimator"]: r for r in rows("fan_vs_truth")}
    facts = {"latest_year": latest, "participants": bounds["identity_participants_point"], "low": bounds["identity_participants_low"], "high": bounds["identity_participants_high"],
             "did_pct": fan["DID_ADDITIVE"]["estimate_pct"], "naive_pct": fan["NAIVE"]["estimate_pct"], "truth_pct": fan["DID_ADDITIVE"]["true_effect_pct"],
             "km1": next(r["km_survival"] for r in rows("retention_km_all") if r["years_since_entry"] == 1)}
    acq = {r["method"][0]: r for r in rows("acq_estimates")}
    aud = next(r for r in rows("audience_latest") if r["household_group"] == "ALL")
    facts.update({"incremental": round(acq["1"]["estimate"]), "inc_low": round(acq["1"]["ci_low"]), "inc_high": round(acq["1"]["ci_high"]), "naive_scaled": round(acq["2"]["estimate"]),
                  "contactable": aud["audience_contactable"], "registered": aud["audience_registered"], "gap": aud["consent_gap_households"], "gap_share": aud["consent_gap_share_of_active"],
                  "audience_month": str(max(r["month"] for r in rows("audience_series")))[:7]})
    if out.exists():
        shutil.rmtree(out)
    (out / "data").mkdir(parents=True)
    for name, d in data.items():
        (out / "data" / f"{name}.json").write_text(json.dumps(d, default=str), encoding="utf-8")
    (out / "data" / "manifest.json").write_text(json.dumps({"datasets": [{"name": n, "source": d["source"], "kind": d["kind"], "rows": len(d["rows"])} for n, d in data.items()]}, indent=1), encoding="utf-8")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    for slug, (title, body) in build_pages(data, chart_defs, facts).items():
        (out / f"{slug}.html").write_text(page(slug, title, body, stamp), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return {"datasets": len(data), "charts": len(chart_defs), "pages": len(PAGES)}


def main() -> int:
    res = build()
    print(f"built site/: {res['pages']} pages, {res['charts']} charts, {res['datasets']} datasets (share_exec, approved aggregates, whitelisted evaluation summaries, governance metadata)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
