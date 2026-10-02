"""Build the static results site (site/) from the warehouse. All data is SYNTHETIC.

  uv run python -m scripts.build_site            (make site)

Rules the build enforces (and tests/test_build_site.py checks):
  * Every number on the site comes from a dataset in the DATASETS list below, exported to site/data/<name>.json. A dataset may read ONLY
      - a `share_exec` table (the executive share: aggregates, small cells suppressed),
      - `share_analyst.share_analyst__fan_event_study` (an approved aggregate: nothing household-level),
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
APPROVED_AGGREGATES = {"share_analyst.share_analyst__fan_event_study"}
EVAL_WHITELIST = {
    "evaluation.eval_threshold_sweep", "evaluation.eval_pairwise", "evaluation.eval_clusters", "evaluation.eval_errors",
    "evaluation.eval_participation_accuracy", "evaluation.eval_retention", "evaluation.eval_fan_effect",
    "evaluation.eval_fan_matching_diagnostics", "evaluation.eval_headcount_overlap", "evaluation.eval_household_linkage",
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
        page="participation", title="Combined reach: participants plus school and recreation program headcounts", datasets=["combined_reach"],
        spec={"data": _src("combined_reach"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "area", "opacity": 0.25, "color": "#d98a2b"}, "encoding": {"x": {"field": "participation_year", "type": "ordinal", "title": "Participation year"},
             "y": {"field": "combined_reach_low", "type": "quantitative", "scale": {"zero": False}, "title": "Children reached"}, "y2": {"field": "combined_reach_high"}}},
            {"mark": {"type": "line", "point": True, "color": "#2b6cb0"}, "encoding": {"x": {"field": "participation_year", "type": "ordinal"},
             "y": {"field": "reported_headcount", "type": "quantitative"}}}]},
        shows="The reported headcount from schools and recreation departments (line) and the range for participants plus that headcount (band): the low end assumes as much overlap as is possible, the high end none.",
        doesnt="A single combined number: aggregates cannot be matched to people, so some children are counted twice, and a PE unit is exposure, not participation. Programs are small cells and are suppressed where few.")
    C["threshold"] = dict(
        page="identity", title="Threshold sweep: precision and recall of the final matcher", datasets=["threshold_sweep"], evaluation=True,
        spec={"data": _src("threshold_sweep"), "width": "container", "height": 300, "mark": {"type": "line", "point": True},
              "encoding": {"x": {"field": "threshold", "type": "quantitative", "title": "Match probability threshold"},
              "y": {"field": "value", "type": "quantitative", "scale": {"domain": [0.9, 1.0]}, "title": "Pairwise precision / recall"},
              "color": {"field": "measure", "type": "nominal", "title": None}}},
        shows="How pairwise precision and recall move as the automatic-merge threshold changes, graded against the synthetic answer key.",
        doesnt="Performance on real data. The population is synthetic: phone numbers never change and one nickname list covers every nickname, so real data would score lower. The threshold was chosen once, before this chart.")
    C["siblings"] = dict(
        page="identity", title="Sibling and twin false merges by threshold", datasets=["sibling_merges_by_threshold"], evaluation=True,
        spec={"data": _src("sibling_merges_by_threshold"), "width": "container", "height": 240, "mark": {"type": "bar"},
              "encoding": {"x": {"field": "threshold", "type": "ordinal", "title": "Match probability threshold"},
              "y": {"field": "sibling_or_twin_false_merges", "type": "quantitative", "title": "Sibling / twin false merges"}}},
        shows="How many times two different children of the same household were merged into one person at each threshold.",
        doesnt="That a merge is harmless: a sibling merge is a privacy incident, which is why the final matcher guards against it and a steward reviews the probable pairs.")
    C["retention_km"] = dict(
        page="retention", title="Retention by entry age band (Kaplan-Meier, with 95% intervals)", datasets=["retention_km_age"],
        spec={"data": _src("retention_km_age"), "width": "container", "height": 320, "layer": [
            {"mark": {"type": "area", "opacity": 0.12}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative", "title": "Years since entry", "axis": {"tickMinStep": 1}},
             "y": {"field": "km_survival_ci_low", "type": "quantitative", "scale": {"domain": [0, 1]}, "axis": {"format": "%", "title": "Still registered"}},
             "y2": {"field": "km_survival_ci_high"}, "color": {"field": "segment_value", "type": "nominal", "title": "Entry age"}}},
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative"},
             "y": {"field": "km_survival", "type": "quantitative"}, "color": {"field": "segment_value", "type": "nominal"}}}]},
        shows="The share of each entry group still registered k years after their first season, treating a player who turns 18 or whose follow-up ends with the data as censored, not gone.",
        doesnt="Why players leave, or what the curves would be for adults continuing after 17 (this synthetic world has no adult continuation). Steps with fewer than 10 players at risk are not shown.")
    C["retention_sex"] = dict(
        page="retention", title="Retention by sex", datasets=["retention_km_sex"],
        spec={"data": _src("retention_km_sex"), "width": "container", "height": 260, "layer": [
            {"mark": {"type": "area", "opacity": 0.15}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative", "title": "Years since entry", "axis": {"tickMinStep": 1}},
             "y": {"field": "km_survival_ci_low", "type": "quantitative", "scale": {"domain": [0, 1]}, "axis": {"format": "%", "title": "Still registered"}},
             "y2": {"field": "km_survival_ci_high"}, "color": {"field": "segment_value", "type": "nominal", "title": "Sex"}}},
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative"},
             "y": {"field": "km_survival", "type": "quantitative"}, "color": {"field": "segment_value", "type": "nominal"}}}]},
        shows="The same retention curve for girls and boys, with intervals that overlap where the difference is within the noise.",
        doesnt="A causal difference. Segments overlap (age and division describe largely the same players) and nobody was assigned to them.")
    C["cohorts"] = dict(
        page="retention", title="Cohort triangle: share of each entry cohort still registered", datasets=["retention_cohorts"],
        spec={"data": _src("retention_cohorts"), "width": "container", "height": 220, "mark": "rect",
              "encoding": {"x": {"field": "years_since_entry", "type": "ordinal", "title": "Years since entry"},
              "y": {"field": "entry_year", "type": "ordinal", "title": "Entry cohort"},
              "color": {"field": "cohort_retention_pct", "type": "quantitative", "scale": {"domain": [0, 1], "scheme": "blues"}, "legend": {"format": "%", "title": "Still registered"}}}},
        shows="The classic triangle: for each entry year, the share of that cohort registered again 0, 1, 2, ... years later (only years that have happened).",
        doesnt="Retention corrected for ageing out: older youth fall off this view because they turn 18, not because they chose to leave. The table below has the corrected column.")
    C["naive_vs_censored"] = dict(
        page="retention", title="Entrants aged 14 to 17: naive vs censored vs the truth", datasets=["retention_vs_truth"], evaluation=True,
        spec={"data": _src("retention_vs_truth"), "width": "container", "height": 300, "mark": {"type": "line", "point": True},
              "encoding": {"x": {"field": "years_since_entry", "type": "quantitative", "title": "Years since entry", "axis": {"tickMinStep": 1}},
              "y": {"field": "survival", "type": "quantitative", "scale": {"domain": [0, 1]}, "axis": {"format": "%", "title": "Still registered"}},
              "color": {"field": "curve", "type": "nominal", "title": None, "legend": {"orient": "bottom", "columns": 1}}}},
        shows="Counting a 17-year-old who turns 18 as someone who quit makes retention look 22 to 24 points worse for this group; treating it as censored lands near the generator's true churn.",
        doesnt="A bias for younger entrants: they do not turn 18 inside the five-year window, so the naive and censored curves coincide for them. This is the reason the censoring rule exists.")
    C["fan_estimates"] = dict(
        page="fandom", title="Does registering a child raise a household's fan engagement? Naive vs matched vs truth", datasets=["fan_vs_truth"], evaluation=True,
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
        page="fandom", title="Event study: mean fan events per month around the first registration", datasets=["fan_event_study"],
        spec={"data": _src("fan_event_study"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "months_since_event", "type": "quantitative", "title": "Months since first registration"},
             "y": {"field": "mean_events", "type": "quantitative", "title": "Events per household-month"}, "color": {"field": "group_name", "type": "nominal", "title": None}}},
            {"mark": {"type": "rule", "strokeDash": [4, 4]}, "encoding": {"x": {"datum": 0, "type": "quantitative"}}}]},
        shows="Matched participants and matched comparisons track each other before registration (the flat pre period supports the design) and separate afterwards.",
        doesnt="A tight estimate: a small gap remains before registration (residual selection), and the pattern repeats with the NFL season. The vertical dashed line is month 0.")
    C["event_study_effect"] = dict(
        page="fandom", title="Event study: participants relative to comparisons, by month", datasets=["fan_event_study_effect"],
        spec={"data": _src("fan_event_study_effect"), "width": "container", "height": 260, "mark": {"type": "bar"},
              "encoding": {"x": {"field": "months_since_event", "type": "quantitative", "title": "Months since first registration"},
              "y": {"field": "effect", "type": "quantitative", "axis": {"format": "%", "title": "Participants vs comparisons"}}}},
        shows="The gap between the two lines above as a share of the comparison level: small and steady before month 0, about a fifth higher after.",
        doesnt="The matched estimate itself, which subtracts the pre-period gap (see the estimates chart). Read this as a check on the design, not as the answer.")
    return C


# ------------------------------------------------------------------ pages
PAGES = [("index", "Overview"), ("participation", "Participation"), ("identity", "Identity"), ("retention", "Retention"), ("fandom", "Fandom"), ("governance", "Governance")]
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
    libs = "".join(f'<script src="{u}"></script>' for u in LIBS)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Counting Flag Football: {esc(title)}</title><style>{CSS}</style></head><body><header><nav><strong>Counting Flag Football</strong>{nav}</nav></header>'
            f'<main><div class="banner"><b>Synthetic data.</b> Every person on this site is generated. Numbers count registered participants in onboarded sources, '
            f'not total participation. Charts marked "synthetic truth" compare the pipeline with the generator\'s answer key, which no real project would have.</div>'
            f'{body}</main><footer>Built {built} by scripts/build_site.py from share_exec exports and whitelisted evaluation summaries. No number on this site is computed in the browser.</footer>'
            f'{libs}<script>{EMBED_JS}</script></body></html>')


def kv(data: dict, name: str) -> dict:
    return {r["measure"]: r for r in data[name]["rows"]}


def build_pages(data: dict, chart_defs: dict, facts: dict) -> dict[str, tuple[str, str]]:
    built = {}
    blocks = {p: [] for p, _ in PAGES}
    for cid, ch in chart_defs.items():
        blocks[ch["page"]].append(chart_block(cid, ch, data))

    flow = " <i>&rarr;</i> ".join(f"<span>{esc(s)}</span>" for s in ["sources", "contracts", "raw", "staging", "identity", "facts", "marts", "shares", "this site"])
    latest = facts["latest_year"]
    built["index"] = ("Overview", f"""
<h1>Counting a participant</h1>
<p>A governed participation data platform, built end to end on <b>synthetic</b> flag football data (the real equivalent would be minors' personal data).
It answers one question carefully: <i>how many people play, who stays, and what does playing do for a household's engagement</i>, and it shows how sure it is.</p>
<div class="flow">{flow}</div>
<p class="note">Five sources (a league CSV, a club API, a federation workbook, school headcounts and a fan feed) are contracted, loaded as-is, cleaned in SQL, resolved to people,
counted by written rules, shared by audience with small numbers suppressed, and published as versioned snapshots. The generator knows the truth, so every claim is graded.</p>
<h2>Headline, {latest}</h2>
<table><tbody>
<tr><td>Unique registered participants</td><td>{fmt_cell(facts['participants'])}</td></tr>
<tr><td>Identity range (low to high)</td><td>{fmt_cell(facts['low'])} to {fmt_cell(facts['high'])}</td></tr>
<tr><td>Matched fan-engagement uplift (linked households)</td><td>{facts['did_pct']:+.1%} (naive says {facts['naive_pct']:+.1%}; truth {facts['truth_pct']:+.1%})</td></tr>
<tr><td>One-year retention of entrants (Kaplan-Meier, all)</td><td>{facts['km1']:.1%}</td></tr>
</tbody></table>
<h2>A five-minute tour</h2>
<ol class="tour">
<li><a href="participation.html">Participation</a>: the number, and the band around it. Why it is a range.</li>
<li><a href="identity.html">Identity</a>: how people are matched, and the cost of a wrong merge (siblings).</li>
<li><a href="retention.html">Retention</a>: who stays, and why a 17-year-old turning 18 is not someone who quit.</li>
<li><a href="fandom.html">Fandom</a>: the naive answer is three times too big; matching gets close.</li>
<li><a href="governance.html">Governance</a>: who sees what, what was suppressed, what changed after publishing.</li>
</ol>
<p class="note">Decisions and their reasons are in the ADRs; the counting rules are in the methodology memo. Both are linked from <a href="governance.html">Governance</a>.</p>""")
    built["participation"] = ("Participation", "<h1>Participation</h1>" + "".join(blocks["participation"]))
    built["identity"] = ("Identity", "<h1>Identity</h1><p class='note'>Matching people across sources is the hard part. The generator's answer key grades it; real projects have no key.</p>"
                         + "".join(blocks["identity"]) + "<h2>Rules vs probabilistic, before any steward review</h2>" + table_html(data["matcher_comparison"])
                         + "<p class='note'><b>What this shows.</b> A rules baseline, a literal Fellegi-Sunter matcher (fs_naive) and the corrected one (fs) on the same data. <b>What it does not show.</b> Real-world accuracy; the sibling and twin merges are the incidents that matter.</p>"
                         + "<h2>Error categories</h2>" + table_html(data["error_categories"]) + "<h2>Identity bounds against the synthetic truth</h2>" + table_html(data["identity_truth_check"]))
    built["retention"] = ("Retention", "<h1>Retention</h1><p class='note'>Kaplan-Meier survival from the first season, computed in SQL. A player who turns 18, or whose follow-up ends with the data, is censored, not counted as gone.</p>"
                          + "".join(blocks["retention"]))
    built["fandom"] = ("Fandom", "<h1>Fandom</h1><p class='note'>Estimates describe households linked to a fan account, under a restricted-zone policy (ADR-009). Nothing household-level is shown.</p>"
                       + "".join(blocks["fandom"]) + "<h2>Why the matched estimate is where it is</h2>" + table_html(data["fan_diagnostics"])
                       + "<h2>Who can be linked</h2>" + table_html(data["link_rate"]) + "<h2>Linkage precision and recall against the synthetic truth</h2>" + table_html(data["household_linkage_vs_truth"]))
    built["governance"] = ("Governance", f"""<h1>Governance</h1>
<h2>Who sees what</h2>{table_html(data['audience_matrix'])}
<p class="note"><b>What this shows.</b> Five audiences, each with a column-level allow list; the executive audience gets aggregates only. <b>What it does not show.</b> Real access control: this is a policy enforced by a build check, not by a database role (ADR-006).</p>
<h2>Suppression example</h2>{table_html(data['suppression_example'])}
<p class="note"><b>What this shows.</b> A count below 10 is hidden (PRIMARY) and, where subtraction would reveal it, a second cell too (SECONDARY). <b>What it does not show.</b> Formal disclosure control; production would use sdcMicro or tau-Argus.</p>
<h2>Data contracts per source</h2>{table_html(data['contract_status'])}
<h2>Onboarding status</h2>{table_html(data['source_status'])}
<h2>What changed after publishing</h2>{table_html(data['restatement_log'])}
<p class="note">Worked examples: a steward decision, the window growing from three to five years, and a methodology bump that only adds KPIs, in <code>docs/reports/restatement_demo.md</code>.</p>
<h2>Documents</h2><ul>
<li><code>docs/methodology/counting-a-participant.md</code>: the counting rules C1 to C15</li>
<li><code>docs/decisions/</code>: ADR-001 to ADR-010, including the linkage governance decision (ADR-009) and the fandom design (ADR-010)</li>
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
