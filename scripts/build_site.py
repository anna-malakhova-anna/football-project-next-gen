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


def check_brand_boundary(out: Path, local_logo: bool = False) -> list[str]:
    """The site must not carry anyone else's mark. Text is easy to review; images are not, so refuse them outright:
    no image files, no <img>/<image>/url(...) references, and every inline SVG must be the project's own mark or a decorative icon.
    The one exception is the git-ignored local logo (local_logo=True, a local build only): exactly img/logo.webp, shown only as the wordmark image."""
    import re
    problems = []
    for f in sorted(out.rglob("*")):
        if local_logo and f == out / "img" / "logo.webp":
            continue
        if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".ico", ".bmp", ".tif", ".tiff", ".heic"}:
            problems.append(f"{f.relative_to(out)}: image files are not allowed on this site (no third-party logos); the project mark is inline SVG")
    if (out / "img").exists() and not local_logo:
        problems.append("site/img exists: the site carries no image directory")
    fav = out / "favicon.svg"
    if not fav.exists() or fav.read_text(encoding="utf-8") != FAVICON:
        problems.append("favicon.svg is missing or is not the project's own mark")
    for f in sorted(out.glob("*.html")):
        text = f.read_text(encoding="utf-8")
        if local_logo:
            text = text.replace('<img class="wordmark-logo" src="img/logo.webp" alt="" width="36" height="36">', "", 1)
        if re.search(r"<img\b|<image\b|<picture\b|<object\b|<embed\b", text, re.I):
            problems.append(f"{f.name}: contains an image element")
        for m in re.finditer(r"<svg\b([^>]*)>", text):
            if 'aria-hidden="true"' not in m.group(1) and 'data-mark="project"' not in m.group(1) and 'class="drive"' not in m.group(1):
                problems.append(f"{f.name}: an inline SVG is neither the project mark, the drive chart nor a decorative icon")
        if re.search(r"\b(?:rel=\"(?:icon|apple-touch-icon|shortcut icon)\"[^>]*href=\"(?!favicon\.svg)|og:image)", text, re.I):
            problems.append(f"{f.name}: an icon or social image other than favicon.svg")
    for f in sorted(out.glob("css/*.css")):
        if re.search(r"url\(\s*['\"]?(?!https://fonts\.)", f.read_text(encoding="utf-8")):
            problems.append(f"{f.name}: references an external or local image with url()")
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


AGE_ORDER = ["0-7", "8-9", "10-11", "12-13", "14-17", "18-29", "30-44", "45+"]
EST_ORDER = ["Naive comparison", "Matched before/after"]
PALETTE = {"turf": "#2F6B4F", "sky": "#3D7CC9", "pylon": "#D9622B", "plum": "#7D4E8E", "sand": "#B8A06A"}


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
            {"mark": {"type": "area", "opacity": 0.25, "color": "#B8A06A"}, "encoding": {"x": {"field": "participation_year", "type": "ordinal", "title": "Participation year"},
             "y": {"field": "combined_reach_low", "type": "quantitative", "scale": {"zero": False}, "title": "Children reached"}, "y2": {"field": "combined_reach_high"}}},
            {"mark": {"type": "line", "point": True, "color": "#3D7CC9"}, "encoding": {"x": {"field": "participation_year", "type": "ordinal"},
             "y": {"field": "reported_headcount", "type": "quantitative"}}}]},
        shows="The reported headcount from schools and recreation departments (line) and the range for participants plus that headcount (band): the low end assumes as much overlap as is possible, the high end none.",
        doesnt="A single combined number: aggregates cannot be matched to people, so some children are counted twice, and a PE unit is exposure, not participation. Programs are small cells and are suppressed where few.")
    C["threshold"] = dict(
        page="trust", title="Threshold sweep: precision and recall of the final matcher", datasets=["threshold_sweep"], evaluation=True,
        spec={"data": _src("threshold_sweep"), "width": "container", "height": 300, "mark": {"type": "line", "point": True},
              "encoding": {"x": {"field": "threshold", "type": "quantitative", "title": "Match probability threshold"},
              "y": {"field": "value", "type": "quantitative", "scale": {"domain": [0.9, 1.0]}, "title": "Pairwise precision / recall"},
              "color": {"field": "measure", "type": "nominal", "title": None}}},
        shows="How pairwise precision and recall move as the automatic-merge threshold changes, graded against the synthetic answer key.",
        doesnt="Performance on real data. The population is synthetic: phone numbers never change and one nickname list covers every nickname, so real data would score lower. The threshold was chosen once, before this chart.")
    C["siblings"] = dict(
        page="trust", title="Sibling and twin false merges by threshold", datasets=["sibling_merges_by_threshold"], evaluation=True,
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
             "y2": {"field": "km_survival_ci_high"}, "color": {"field": "segment_value", "type": "nominal", "title": "Entry age", "sort": AGE_ORDER, "scale": {"domain": AGE_ORDER}}}},
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative"},
             "y": {"field": "km_survival", "type": "quantitative"}, "color": {"field": "segment_value", "type": "nominal", "sort": AGE_ORDER, "scale": {"domain": AGE_ORDER}}}}]},
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
              "color": {"field": "curve", "type": "nominal", "title": None, "legend": {"orient": "bottom", "columns": 1}},
              "strokeDash": {"field": "curve", "type": "nominal", "legend": None,
                             "scale": {"domain": ["true (generator parameters)", "Kaplan-Meier (age-outs censored)", "naive (age-out counted as churn)"], "range": [[1, 0], [1, 0], [6, 4]]}}}},
        shows="Counting a 17-year-old who turns 18 as someone who quit makes retention look 22 to 24 points worse for this group; treating it as censored lands near the generator's true churn.",
        doesnt="A bias for younger entrants: they do not turn 18 inside the five-year window, so the naive and censored curves coincide for them. This is the reason the censoring rule exists.")
    C["fan_estimates"] = dict(
        page="value", title="Does registering a child raise a household's fan engagement? Naive vs matched vs truth", datasets=["fan_vs_truth"], evaluation=True,
        spec={"data": _src("fan_vs_truth"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "bar", "opacity": 0.8}, "encoding": {"x": {"field": "estimator", "type": "nominal", "title": None, "sort": EST_ORDER},
             "y": {"field": "estimate_pct", "type": "quantitative", "axis": {"format": "%", "title": "Change in events per household-month"}}}},
            {"mark": {"type": "rule", "strokeWidth": 2}, "encoding": {"x": {"field": "estimator", "type": "nominal", "sort": EST_ORDER},
             "y": {"field": "ci_low_pct", "type": "quantitative"}, "y2": {"field": "ci_high_pct"}}},
            {"mark": {"type": "tick", "color": "#D9622B", "thickness": 3, "size": 70}, "encoding": {"x": {"field": "estimator", "type": "nominal", "sort": EST_ORDER},
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
            {"mark": {"type": "tick", "color": "#D9622B", "thickness": 3, "size": 90}, "encoding": {"x": {"field": "method", "type": "nominal", "sort": ORDER}, "y": {"field": "true_incremental_accounts", "type": "quantitative"}}}]},
        shows="The estimate of accounts that exist because of the programme (left, with its interval) next to two naive counts of households that joined after registering, and the number the generator built in (red tick).",
        doesnt="A real programme's effect. Naive counts treat every new account of a registered household as caused by the programme (the scaled one assumes unlinked households behave like linked ones); the estimate compares launching markets with markets that had not launched yet, and is only as good as that comparison.")
    C["drive"] = dict(
        page="acquisition", title="The drive chart: from registered household to active fan", datasets=["drive_stages"], spec=None, render=render_drive,
        shows="Registered households of the latest month moving down the field: how many are linked to a fan account, how many of those a guardian has opted in (contactable), and how many are active. The bar narrows in proportion to the count.",
        doesnt="A strict funnel or the full journey: contactable and active are both shares of linked households and overlap (some active households have no opt-in), and monetized and retained fans are not in the executive share yet. Unlinked households sit in their own lane because unlinked means unknown, not non-fan.")
    C["funnel_status"] = dict(
        page="acquisition", title="What fan status do registered households have?", datasets=["fan_status_mix"],
        spec={"data": _src("fan_status_mix"), "width": "container", "height": 280, "mark": "bar",
              "encoding": {"x": {"field": "households", "type": "quantitative", "title": "Registered households, latest cohort"}, "y": {"field": "fan_status", "type": "nominal", "sort": "-x", "title": None}}},
        shows="Every registered household of the latest cohort by fan status. UNLINKED (no fan account found) is the largest group and means unknown, not non-fan.",
        doesnt="How many unlinked households really are fans: some have an account the identity link could not find. Without identity resolution, multi-league kids would also inflate this household count.")
    C["funnel_rates"] = dict(
        page="acquisition", title="The funnel: from fan to active to contactable to paying", datasets=["funnel_rates"],
        spec={"data": _src("funnel_rates"), "width": "container", "height": 300, "mark": "bar",
              "encoding": {"x": {"field": "stage", "type": "nominal", "title": None, "sort": ["Active (of linked)", "Contactable (of linked)", "Monetized (of active)"], "axis": {"labelAngle": 0, "labelLimit": 200}}, "xOffset": {"field": "fan_status", "type": "nominal"},
              "y": {"field": "rate", "type": "quantitative", "axis": {"format": "%", "title": "Share of the previous step"}}, "color": {"field": "fan_status", "type": "nominal", "title": "Fan status"}}},
        shows="For linked households of the latest cohort, the share that are active, contactable and monetized, by fan status. Step 3 is a share of active households.",
        doesnt="Unlinked households (they have no account to be active or contactable) or causes: existing fans differ from net-new fans before they ever register a child.")
    C["acq_event_study"] = dict(
        page="acquisition", title="Event study: new accounts per 1,000 households, by years since a market launched", datasets=["acq_event_study"], evaluation=True,
        spec={"data": _src("acq_event_study"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "area", "opacity": 0.2}, "encoding": {"x": {"field": "years_since_launch", "type": "ordinal", "title": "Years since launch (year -1 is the reference year)", "axis": {"labelAngle": 0}},
             "y": {"field": "ci_low", "type": "quantitative", "title": "Extra new accounts per 1,000 households"}, "y2": {"field": "ci_high"}}},
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "years_since_launch", "type": "ordinal"}, "y": {"field": "estimate", "type": "quantitative"}}},
            {"mark": {"type": "tick", "color": "#D9622B", "thickness": 3, "size": 18, "orient": "horizontal"}, "encoding": {"x": {"field": "years_since_launch", "type": "ordinal"}, "y": {"field": "truth", "type": "quantitative"}}}]},
        shows="The extra new accounts in launched markets compared with markets that had not launched yet, by year since launch, with intervals. The only pre-launch point (two years before launch) sits near zero, which is thin support for the comparison, not a pre-trend test; red ticks are the built-in truth.",
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
              "encoding": {"x": {"field": "participation_per_1000", "type": "quantitative", "title": "Participant households per 1,000 households"}, "y": {"field": "fan_accounts_per_1000", "type": "quantitative", "scale": {"zero": False}, "title": "Fan accounts per 1,000 households"},
              "color": {"field": "quadrant", "type": "nominal", "title": "Quadrant"}, "tooltip": [{"field": "market_name"}, {"field": "quadrant"}]}},
        shows="Each synthetic market with enough participant households, by participation and fan accounts per 1,000 households, coloured by quadrant (cut-offs are the medians).",
        doesnt="Real places: the markets are invented. Markets with too few participant households are rolled up and not drawn, and a quadrant says where to look, not what to do.")
    # notes that sit under a chart; each gets the exported datasets and returns plain text built from them
    C["participation_trend"]["note"] = note_participation_trend
    C["funnel_rates"]["note"] = lambda d: ("Dormant lapsed households have no bars for Active and Monetized: they are zero by definition (a household that is still dormant is not active, so it cannot be monetized), "
                                           "not missing data.")
    C["acq_event_study"]["note"] = lambda d: ("Only one pre-launch year (two years before launch) is observed, because every market in this synthetic world launches in year 1 or later and year -1 is the reference year. "
                                              "A flat pre-period therefore rests on a single point.")
    C["market_quadrants"]["note"] = note_market_quadrants
    return C


def note_participation_trend(d):
    rows = {r["participation_year"]: r for r in d["participation_bounds"]["rows"]}
    first, last = min(rows), max(rows)
    widest = max((r["identity_participants_high"] - r["identity_participants_low"]) / r["identity_participants_point"] for r in rows.values())
    return (f"The identity band is too narrow to see on this scale: at its widest it is {widest:.1%} of the count, so the line and the band overlap (the numbers are in the table below). "
            f"The rise from {rows[first]['identity_participants_point']:,} in {first} to {rows[last]['identity_participants_point']:,} in {last} is mostly markets launching in successive years in this synthetic world, "
            "so it is not the same programme growing sixfold.")


def note_market_quadrants(d):
    fan = [r["fan_accounts_per_1000"] for r in d["market_scatter"]["rows"]]
    lo, hi = min(fan), max(fan)
    return (f"The vertical split is weak: every market shown has between {lo:.1f} and {hi:.1f} fan accounts per 1,000 households, so the gap between a \"thin\" and a \"strong\" fan base is at most "
            f"{hi - lo:.1f} accounts per 1,000. The axis is zoomed to show that spread; read the horizontal split (participation) with more confidence than the vertical one.")


# ------------------------------------------------------------------ drive chart (server-side SVG, geometry precomputed: ui-spec 4.1)
def render_drive(d: dict) -> str:
    rows = {r["step"]: r for r in d["drive_stages"]["rows"]}
    W, H_FIELD, TOP, BOTTOM, LANE_Y, LANE_H = 720, 230, 46, 44, 246, 40
    seg = W / 4
    max_bar = H_FIELD - TOP - BOTTOM
    total = rows[1]["households"]
    cy = TOP + max_bar / 2
    half = lambda n: max(3.0, max_bar * n / total / 2)  # noqa: E731
    out = [f'<svg class="drive" viewBox="0 0 {W} {LANE_Y + LANE_H + 6}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Drive chart: households at each stage from registered to active, with unlinked households in a separate lane">',
           '<defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="8" fill="#1d3550"/><line x1="0" y1="0" x2="0" y2="8" stroke="#8A96A3" stroke-width="2" opacity=".55"/></pattern></defs>',
           f'<rect x="0" y="0" width="{W}" height="{H_FIELD}" fill="#14263B"/>']
    for i in range(1, 4):
        out.append(f'<line x1="{seg * i:.0f}" y1="8" x2="{seg * i:.0f}" y2="{H_FIELD - 8}" stroke="#F4F6F1" stroke-opacity=".22" stroke-width="1"/>')
    heights = [half(rows[k]["households"]) for k in (1, 2, 3, 4)]
    for i, k in enumerate((1, 2, 3, 4)):
        x0, x1 = seg * i, seg * (i + 1)
        h_in = heights[i - 1] if i else heights[0]
        h_out = heights[i]
        out.append(f'<polygon points="{x0:.1f},{cy - h_in:.1f} {x1:.1f},{cy - h_out:.1f} {x1:.1f},{cy + h_out:.1f} {x0:.1f},{cy + h_in:.1f}" fill="#4C9A73" fill-opacity="{0.95 - i * 0.12:.2f}"/>')
        r = rows[k]
        label = "" if k == 1 else f" · {r['conversion']:.0%} of {r['conversion_base'].split()[0]}"
        out.append(f'<text x="{x0 + 10:.0f}" y="24" fill="#F4F6F1" font-size="16" font-weight="700">{esc(r["stage"])}</text>')
        out.append(f'<text x="{x0 + 10:.0f}" y="{H_FIELD - 22}" fill="#F4F6F1" font-size="15">{r["households"]:,}</text>')
        if label:
            out.append(f'<text x="{x0 + 10:.0f}" y="{H_FIELD - 7}" fill="#B4C0CC" font-size="12">{esc(label.removeprefix(" · "))}</text>')
    out.append(f'<line x1="{W - 2}" y1="6" x2="{W - 2}" y2="{H_FIELD - 6}" stroke="#F2C230" stroke-width="3"/>')
    u = rows[5]
    out.append(f'<rect x="0" y="{LANE_Y}" width="{W}" height="{LANE_H}" fill="url(#hatch)"/>')
    out.append(f'<text x="12" y="{LANE_Y + 25}" fill="#F4F6F1" font-size="14" font-weight="700">Unknown fan status (no linked account) · {u["households"]:,} households · {u["conversion"]:.0%} of registered</text>')
    out.append('</svg>')
    return "".join(out)


# ------------------------------------------------------------------ pages
PAGES = [("index", "Overview"), ("acquisition", "Acquisition"), ("value", "Value"), ("audience", "Audience"), ("participation", "Participation"), ("trust", "Trust")]
# page title (display type) and the one-sentence question under it (ui-spec section 5)
PAGE_HEAD = {
    "index": ("Counting flag football's fans", "What this project is and how to read it."),
    "acquisition": ("Fan acquisition", "How many families become fans, and how many are new?"),
    "value": ("Fan value and activeness", "How engaged and valuable are flag families?"),
    "audience": ("Audience and consent", "How many can we reach, and what are we missing?"),
    "participation": ("Participation", "How many play, and how sure are we?"),
    "trust": ("Data trust and governance", "Why can these numbers be trusted?"),
    "appendix": ("Appendix: school and recreation programs", "A stretch source: how many children do schools and recreation departments report?"),
}
SRC = ROOT / "site_src"
LOCAL_LOGO = ROOT / "local_assets" / "logo.webp"       # optional and git-ignored: shown on a local build only, so CI and the published site never carry it
APPENDIX = [("appendix", "Appendix")]          # a stretch source (school and recreation headcounts): built, linked from the footer, not in the main navigation

# Plain labels for code names. Values are relabelled in the exported rows (so charts and tables agree); headers are relabelled when a table is drawn.
# Source lines (the <code> under each table title) keep the model names on purpose.
FAN_STATUS = {"EXISTING_ACTIVE": "Existing fan, active", "LAPSED_DORMANT": "Lapsed, still dormant", "LAPSED_REACTIVATED": "Lapsed, reactivated",
              "NET_NEW": "Net-new fan", "UNLINKED": "Unlinked (status unknown)"}
FAN_GROUP = {"EXISTING_FAN": "Existing fans", "NET_NEW_FLAG_PROMPT": "Net-new, prompted by flag", "NET_NEW_OTHER": "Net-new, other route",
             "UNLINKED_OR_NON_PARTICIPANT": "Unlinked or non-participant", "UNLINKED": "Unlinked (status unknown)", "ALL": "All households"}
SOURCE_NAMES = {"US_LEAGUE": "US league", "CA_CLUB": "Canadian club", "INTL_FED": "International federation", "SCHOOL_AGGREGATES": "School and recreation programs",
                "FAN_ENGAGEMENT": "Fan app and ticketing"}
VALUE_LABELS = {
    "fan_status_mix": {"fan_status": FAN_STATUS}, "funnel_rates": {"fan_status": FAN_STATUS},
    "fan_rfm_latest": {"fan_group": FAN_GROUP}, "fan_survival": {"fan_group": FAN_GROUP}, "fan_ltv": {"fan_group": FAN_GROUP}, "audience_latest": {"household_group": FAN_GROUP},
    "fan_vs_truth": {"estimator": {"NAIVE": "Naive comparison", "DID_ADDITIVE": "Matched before/after"}},
    "fan_effect": {"estimator": {"NAIVE": "Naive comparison", "DID_ADDITIVE": "Matched before/after"}},
    "uplift_events": {"uplift_status_group": {"ALL": "All linked households", "EXISTING": "Existing fans", "LAPSED": "Lapsed fans"}},
    "uplift_spend": {"uplift_status_group": {"ALL": "All linked households", "EXISTING": "Existing fans", "LAPSED": "Lapsed fans"}},
    "consent_by_capture_point": {"capture_point": {"checkout": "Checkout", "flag_registration": "Flag registration", "preference_center": "Preference center", "signup": "Sign-up"},
                                 "channel": {"email": "Email", "sms": "SMS", "push": "Push"}},
    "suppression_example": {"sex": {"F": "Female", "M": "Male", "U": "Unknown"}, "suppressed": {"NONE": "shown", "PRIMARY": "hidden: count below 10", "SECONDARY": "hidden: protects a hidden cell"}},
    "link_rate": {"country_code": {"ALL": "All countries"}},
    "matcher_comparison": {"matcher": {"rules": "Rules only", "fs_naive": "Probabilistic, uncorrected", "fs": "Probabilistic, final"},
                           "scope": {"AUTO": "Automatic merges only", "AUTO_PLUS_PROBABLE": "Automatic plus probable"}},
    "error_categories": {"matcher": {"rules": "Rules only", "fs_naive": "Probabilistic, uncorrected", "fs": "Probabilistic, final"},
                         "error_type": {"FALSE_NEGATIVE": "Missed match", "FALSE_POSITIVE": "False merge"},
                         "likely_cause": {"BELOW_THRESHOLD": "Below the threshold", "BLOCKING_MISS": "Never compared", "GUARD_OVERRIDE": "Blocked by the household guard",
                                          "NAME_CHANGE": "Name changed", "OTHER": "Other", "TRANSITIVE_CHAIN": "Joined through a chain of matches", "TWIN": "Twins or siblings"}},
    "fan_diagnostics": {"measure": {
        "comparison_contamination": "Comparison households that later registered a child (share)",
        "fandom_matched_comparison": "Underlying fandom, matched comparison households",
        "fandom_matched_treated": "Underlying fandom, matched participating households",
        "fandom_non_participants": "Underlying fandom, all non-participating households",
        "fandom_participants": "Underlying fandom, all participating households",
        "matched_pre_period_gap_pct": "Gap before registration, matched",
        "pretrend_max_abs_effect_pct": "Largest monthly gap before registration, matched",
        "pretrend_mean_effect_pct": "Average monthly gap before registration, matched",
        "unmatched_post_period_gap_pct": "Gap after registration, unmatched",
        "unmatched_pre_period_gap_pct": "Gap before registration, unmatched"}},
    "household_linkage_vs_truth": {"measure": {"link_rate_of_all_participant_households": "Share of all participant households linked", "precision": "Precision",
                                               "precision_EMAIL": "Precision, matched on email", "precision_PHONE": "Precision, matched on phone", "recall": "Recall",
                                               "recall_linkable": "Recall, linkable households only"}},
    "contract_status": {"source_system": SOURCE_NAMES}, "source_status": {"source_system": SOURCE_NAMES},
}
COLUMN_LABELS = {
    "participation_year": "Year", "identity_participants_low": "Participants, low", "identity_participants_point": "Participants", "identity_participants_high": "Participants, high",
    "country_code": "Country", "view": "View", "participants": "Participants", "girls_share_of_youth": "Girls' share of youth", "reported_headcount": "Reported headcount",
    "combined_reach_low": "Combined reach, low", "combined_reach_high": "Combined reach, high", "sex": "Sex", "suppressed": "Status",
    "segment_value": "Group", "years_since_entry": "Years since entry", "km_at_risk": "Players at risk", "km_survival": "Still registered", "km_survival_ci_low": "Interval, low",
    "km_survival_ci_high": "Interval, high", "entry_year": "Entry year", "entry_cohort_size": "Cohort size", "cohort_retention_pct": "Still registered",
    "cohort_retention_among_eligible_pct": "Still registered, excluding age-outs", "estimator": "Method", "fan_uplift_pct": "Uplift", "fan_uplift_ci_low_pct": "Interval, low",
    "fan_uplift_ci_high_pct": "Interval, high", "fan_treated_households": "Households", "caveat": "Caveat", "program_households": "Participant households",
    "linked_households": "Linked households", "household_link_rate": "Link rate", "months_since_event": "Months since registration", "group_name": "Group", "mean_events": "Events per household-month",
    "effect": "Participants vs comparisons", "threshold": "Threshold", "measure": "Measure", "value": "Value", "sibling_or_twin_false_merges": "Sibling or twin false merges",
    "review_items_if_review": "Items for review", "matcher": "Matcher", "scope": "Scope", "precision": "Precision", "recall": "Recall", "f1": "F1", "sibling_twin_merges": "Sibling or twin false merges",
    "predicted_participants": "Participants found", "true_participants": "True participants", "error_type": "Error", "likely_cause": "Likely cause", "pairs": "Pairs",
    "participants_low": "Low", "participants_point": "Point", "participants_high": "High", "truth_within_range": "Truth inside range", "curve": "Curve", "survival": "Still registered",
    "estimate_pct": "Estimate", "ci_low_pct": "Interval, low", "ci_high_pct": "Interval, high", "true_effect_pct": "True effect", "true_uplift_parameter": "Built-in uplift",
    "estimate_over_truth": "Estimate / truth", "truth_in_ci": "Truth inside interval", "true_combined_reach": "True combined reach", "truth_inside_range": "Truth inside range", "naive_sum": "Naive sum",
    "n": "Count", "fan_status": "Fan status", "households": "Households", "stage": "Step", "rate": "Share", "fan_group": "Fan group", "segment": "RFM segment", "rfm_share": "Share of group",
    "months_since_origin": "Months since account began", "survival_at_risk": "Accounts at risk", "fan_survival": "Not lapsed", "fan_survival_ci_low": "Interval, low", "fan_survival_ci_high": "Interval, high",
    "value_accounts": "Accounts", "fan_ltv": "Value per account", "fan_ltv_low": "Low", "fan_ltv_high": "High", "horizon_months": "Horizon (months)", "currency_label": "Currency",
    "uplift_status_group": "Status before registering", "uplift_households": "Households", "uplift_per_month": "Extra per household-month", "uplift_ci_low_per_month": "Interval, low",
    "uplift_ci_high_per_month": "Interval, high", "month": "Month", "household_group": "Household group", "audience_registered": "Registered", "audience_linked": "Linked",
    "audience_contactable": "Contactable", "audience_contactable_email": "Contactable by email", "audience_contactable_sms": "Contactable by SMS", "audience_contactable_push": "Contactable by push",
    "audience_active": "Active", "consent_gap_households": "Consent gap (households)", "consent_gap_share_of_active": "Consent gap, share of active", "consent_gap_value": "Value of the gap (synthetic currency)",
    "capture_point": "Capture point", "channel": "Channel", "consent_lines": "Consent records", "consent_opt_in_rate": "Opt-in rate", "market_name": "Market", "quadrant": "Quadrant",
    "participant_households": "Participant households", "participation_per_1000": "Participants per 1,000", "fan_accounts_per_1000": "Fan accounts per 1,000", "markets_shown": "Markets shown",
    "markets": "Markets", "method": "Method", "estimate": "Estimate", "ci_low": "Interval, low", "ci_high": "Interval, high", "true_incremental_accounts": "True incremental accounts",
    "years_since_launch": "Years since launch", "truth": "Truth", "source_system": "Source", "component": "Component", "contract_version": "Contract version", "pass": "Passed", "warn": "Warnings",
    "error": "Errors", "onboarding_status": "Onboarding status", "description": "Description", "audience": "Audience", "share_tables": "Share tables", "columns_allowed": "Columns allowed",
    "columns_denied": "Columns denied", "kpi_rows": "KPI rows", "kpis": "KPIs", "restatement_required": "Restatements required", "step": "Step", "conversion": "Conversion", "conversion_base": "Share of",
    "true_survival": "True",
}
ID_COLUMNS = {"participation_year", "entry_year", "years_since_entry", "years_since_launch", "months_since_event", "months_since_origin", "horizon_months", "step"}
RATE_COLUMNS = {"girls_share_of_youth", "km_survival", "km_survival_ci_low", "km_survival_ci_high", "cohort_retention_pct", "cohort_retention_among_eligible_pct", "household_link_rate",
                "survival", "rate", "rfm_share", "fan_survival", "fan_survival_ci_low", "fan_survival_ci_high", "consent_gap_share_of_active", "consent_opt_in_rate", "conversion"}


def relabel(data: dict) -> None:
    for name, cols in VALUE_LABELS.items():
        for r in data[name]["rows"]:
            for c, mapping in cols.items():
                r[c] = mapping.get(r[c], r[c])


def esc(v) -> str:
    return html.escape(str(v))


def fmt_cell(v, col: str = "") -> str:
    """Counts get thousands separators; years, months and similar identifiers stay plain; rates in [0, 1] show as percentages."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if col in RATE_COLUMNS or col.endswith("_pct"):
        if isinstance(v, (int, float)) and abs(v) <= 5:
            return f"{v:.1%}"
    if isinstance(v, float):
        return f"{v:.4f}" if abs(v) < 10 else f"{v:,.1f}"
    if isinstance(v, int):
        return f"{v:,}" if col not in ID_COLUMNS else str(v)
    return str(v)


def table_html(ds: dict, limit: int = 60) -> str:
    cols, rows = ds["columns"], ds["rows"][:limit]
    if not rows:
        return f"<p class='note'><b>No rows.</b> The query returned nothing, which is the expected result when {esc(ds['title'].lower())} has nothing to report.</p>"
    head = "".join(f"<th>{esc(COLUMN_LABELS.get(c, c))}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{esc(fmt_cell(r[c], c))}</td>" for c in cols) + "</tr>" for r in rows)
    more = f"<p class='note'>First {limit} of {len(ds['rows'])} rows; the full file is data/{ds['name']}.json.</p>" if len(ds["rows"]) > limit else ""
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>{more}"


def chart_block(cid: str, ch: dict, data: dict) -> str:
    tag = '<span class="tag">synthetic truth, evaluation only</span>' if ch.get("evaluation") else ""
    tables = "".join(f"<p class='note'><b>{esc(data[n]['title'])}</b> <code>{esc(data[n]['source'])}</code></p>{table_html(data[n])}" for n in ch["datasets"])
    plot = ch["render"](data) if ch.get("render") else f'<div id="{cid}" role="img" aria-label="{esc(ch["title"])}"></div>'
    script = f'<script type="application/json" data-chart="{cid}">{json.dumps(ch["spec"])}</script>' if ch.get("spec") else ""
    note = f'<p class="note"><b>Reading note.</b> {esc(ch["note"](data))}</p>' if ch.get("note") else ""
    return (f'<section class="chart" id="sec-{cid}"><h3>{esc(ch["title"])}{tag}</h3>{plot}'
            f'<p class="note"><b>What this shows.</b> {esc(ch["shows"])}</p><p class="note"><b>What it does not show.</b> {esc(ch["doesnt"])}</p>{note}'
            f'<details><summary>The numbers behind this chart</summary>{tables}</details>'
            f'{script}</section>')


def render_page(slug: str, body: str, built: str, version: str) -> str:
    """Render one page through the Jinja base template (site_src/templates/base.html)."""
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    env = Environment(loader=FileSystemLoader(str(SRC / "templates")), autoescape=True, undefined=StrictUndefined)
    title, question = PAGE_HEAD[slug]
    return env.get_template("base.html").render(title=title, question=question, body=body, built=built, version=version, libs=LIBS,
                                                nav=[(sl, lb) for sl, lb in PAGES if sl != "index"], current=slug, appendix=True, logo=LOCAL_LOGO.exists())


FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" fill="#2F6B4F"/>'
           '<rect x="4" y="14" width="24" height="4" fill="#F2C230"/></svg>')


def copy_assets(out: Path) -> None:
    (out / "css").mkdir(parents=True, exist_ok=True)
    (out / "js").mkdir(parents=True, exist_ok=True)
    for name in ("tokens.css", "site.css"):
        shutil.copy(SRC / "styles" / name, out / "css" / name)
    shutil.copy(SRC / "site.js", out / "js" / "site.js")
    (out / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    if LOCAL_LOGO.exists():
        (out / "img").mkdir(exist_ok=True)
        shutil.copy(LOCAL_LOGO, out / "img" / "logo.webp")


def kv(data: dict, name: str) -> dict:
    return {r["measure"]: r for r in data[name]["rows"]}


def value_explanation(f: dict) -> str:
    """One plain paragraph on how the estimates sit against the synthetic truth. Direction-aware, so it stays honest if the numbers move."""
    naive, did, truth = f["naive_pct"], f["did_pct"], f["truth_pct"]
    parts = [f"The naive comparison says {naive:+.1%}, the matched estimate {did:+.1%}, and the uplift built into the data is {truth:+.1%}."]
    if naive < truth:
        parts.append("Unlike the acquisition and retention charts, the naive number does not overstate here: it comes in below the truth.")
    if did > truth:
        parts.append("The matched estimate overshoots the truth. The table below points to why: "
                     f"matching on observed engagement did not balance the underlying fan inclination, which averages {f['fandom_treated']:.2f} for the matched participating households "
                     f"against {f['fandom_comparison']:.2f} for their matched comparisons, so the before/after change still leans high. "
                     "Read the matched figure as an upper-leaning estimate, not a correction.")
    return "<p class='note'>" + esc(" ".join(parts)) + "</p>"


RESTATEMENT_EXAMPLES = """<p class="note">The restatement log is empty because the latest published snapshots match the rebuilt numbers. That is the good case. Four recorded runs show what it looks like when it is not empty
(full tables in <code>docs/reports/restatement_demo.md</code>; all synthetic):</p>
<table><thead><tr><th>Example</th><th>Cause</th><th>What changed</th><th>Restatement?</th></tr></thead><tbody>
<tr><td>One steward decision</td><td>Identity change</td><td>Two registrations of one child, kept apart by a mistyped first name, were merged. 2025 unique participants went from 3,962 to 3,961 (-0.025%).</td><td>No: below the 1% threshold; logged for the next snapshot</td></tr>
<tr><td>The observation window grew from 3 to 5 years</td><td>New source data</td><td>41 changed KPIs; 23 exceeded the threshold. 2025 unique participants went from 3,962 to 2,837 (-28.4%).</td><td>Yes: three published years restated, new baselines published</td></tr>
<tr><td>A methodology bump that only adds KPIs</td><td>New KPI</td><td>Four school and recreation KPIs added for five years. Every existing KPI was identical to its published value.</td><td>No: additions are listed, never restated</td></tr>
<tr><td>The generator changed upstream (more people, staggered market launches)</td><td>New source data</td><td>88 changed KPI rows; 59 required a restatement. 2025 unique participants went from 2,837 to 8,959 (+215.8%).</td><td>Yes: methodology v2.0 published new baselines</td></tr>
</tbody></table>"""


def build_pages(data: dict, chart_defs: dict, facts: dict) -> dict[str, tuple[str, str]]:
    built = {}
    blocks = {p: [] for p, _ in PAGES + APPENDIX}
    for cid, ch in chart_defs.items():
        blocks[ch["page"]].append(chart_block(cid, ch, data))

    flow = " <i>&rarr;</i> ".join(f"<span>{esc(s)}</span>" for s in ["sources", "contracts", "raw", "staging", "identity", "households", "fan models", "shares", "this site"])
    latest = facts["latest_year"]
    built["index"] = ("Overview", f"""
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
<li><a href="trust.html">Data trust &amp; governance</a>: identity resolution (why the household count is right), contracts, who sees what, what changed after publishing.</li>
</ol>
<p class="note">Decisions and their reasons are in the ADRs; the counting rules are in the methodology memos. Both are linked from <a href="trust.html">Data trust &amp; governance</a>.</p>""")
    built["acquisition"] = ("Fan acquisition", "<p class='note'>How many fans did the programme create? The first chart is the answer; the rest show where it comes from. Funnel and status describe households linked to a fan account; "
                            "identity resolution is why the denominator is right (a child in several leagues is one household member, not several).</p>" + "".join(blocks["acquisition"]))
    built["value"] = ("Fan value & activeness", "<p class='note'>Estimates describe households linked to a fan account, under a restricted-zone policy (ADR-009). Nothing household-level is shown; money is synthetic currency.</p>"
                      + "".join(blocks["value"]) + "<h2>Why the matched engagement estimate is where it is</h2>" + value_explanation(facts) + table_html(data["fan_diagnostics"]))
    built["audience"] = ("Audience & consent", "<p class='note'>Governance determines the size of the marketable audience: only a guardian's recorded opt-in makes a household contactable. "
                         "Counts only; nobody here is a list, and no linked household reaches marketing or media (ADR-009).</p>"
                         + "".join(blocks["audience"]) + "<h2>Latest month by household group</h2>" + table_html(data["audience_latest"])
                         + "<h2>Markets per quadrant</h2>" + table_html(data["quadrant_counts"])
                         + "<h2>Who can be linked</h2>" + table_html(data["link_rate"]))
    built["participation"] = ("Participation", "<p class='note'>The original question, condensed: how many people play, with the band that identity resolution leaves, and who stays. Retention is Kaplan-Meier from the first season, computed in SQL: "
                              "a player who turns 18, or whose follow-up ends with the data, is censored, not counted as gone.</p>" + "".join(blocks["participation"]))
    built["appendix"] = ("Appendix", "<p class='note'>A <b>stretch</b> source: school districts and recreation departments report how many "
                         "children are in their programs. The counts have no people in them, so they are never added to participants.</p>" + "".join(blocks["appendix"])
                         + "<h2>Against the synthetic truth</h2>" + table_html(data["reach_vs_truth"]))
    built["trust"] = ("Trust", f"""<h2>Identity: can the numbers be trusted?</h2>
<p class='note'>Matching people across sources is the hard part. The generator's answer key grades it; real projects have no key.</p>
{"".join(blocks["trust"])}
<h3>Rules vs probabilistic, before any steward review</h3>{table_html(data["matcher_comparison"])}
<p class="note"><b>What this shows.</b> A rules baseline, a literal Fellegi-Sunter matcher (fs_naive) and the corrected one (fs) on the same data. <b>What it does not show.</b> Real-world accuracy; the sibling and twin merges are the incidents that matter.</p>
<h3>Error categories</h3>{table_html(data["error_categories"])}
<h3>Identity bounds against the synthetic truth</h3>{table_html(data["identity_truth_check"])}
<h3>Household linkage precision and recall against the synthetic truth</h3>{table_html(data["household_linkage_vs_truth"])}
<h2>Who sees what</h2>{table_html(data['audience_matrix'])}
<p class="note"><b>What this shows.</b> Five audiences, each with a column-level allow list; the executive audience gets aggregates only, and nothing linked reaches marketing or media. <b>What it does not show.</b> Real access control: this is a policy enforced by a build check, not by a database role (ADR-006).</p>
<h2>Suppression example</h2><p class="note">Participants by sex, every year. In 2021, 2022 and 2024 the count of participants with unknown sex is below 10 and is hidden, and so is the female count, because the total and the male count would reveal it by subtraction.</p>{table_html(data['suppression_example'])}
<p class="note"><b>What this shows.</b> A count below 10 is hidden (primary suppression) and, where subtraction would reveal it, a second cell too (secondary suppression). <b>What it does not show.</b> Formal disclosure control; production would use sdcMicro or tau-Argus.</p>
<h2>Data contracts per source</h2>{table_html(data['contract_status'])}
<h2>Onboarding status</h2>{table_html(data['source_status'])}
<h2>What changed after publishing</h2>{table_html(data['restatement_log']) if data['restatement_log']['rows'] else ''}{RESTATEMENT_EXAMPLES}
<h2 id="documents">Documents</h2><ul>
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
        con_version = con.execute("select max(methodology_version) from measurement.mart_kpi_scorecard").fetchone()[0]
    finally:
        con.close()
    chart_defs = charts()
    known = {f"data/{n}.json" for n in data}
    problems = [p for cid, ch in chart_defs.items() if ch.get("spec") for p in check_spec(ch["spec"], known, cid)]
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
    diag = {r["measure"]: r["value"] for r in rows("fan_diagnostics")}
    facts.update({"fandom_treated": diag["fandom_matched_treated"], "fandom_comparison": diag["fandom_matched_comparison"]})
    relabel(data)                       # plain labels for every code name, after the facts above have used the codes
    if out.exists():
        shutil.rmtree(out)
    (out / "data").mkdir(parents=True)
    for name, d in data.items():
        (out / "data" / f"{name}.json").write_text(json.dumps(d, default=str), encoding="utf-8")
    (out / "data" / "manifest.json").write_text(json.dumps({"datasets": [{"name": n, "source": d["source"], "kind": d["kind"], "rows": len(d["rows"])} for n, d in data.items()]}, indent=1), encoding="utf-8")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    version = con_version
    copy_assets(out)
    for slug, (_title, body) in build_pages(data, chart_defs, facts).items():
        (out / f"{slug}.html").write_text(render_page(slug, body, stamp, version), encoding="utf-8")
    problems = check_brand_boundary(out, local_logo=LOCAL_LOGO.exists())
    if problems:
        shutil.rmtree(out)
        raise SystemExit("SITE BUILD REFUSED:\n  " + "\n  ".join(problems))
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return {"datasets": len(data), "charts": len(chart_defs), "pages": len(PAGES)}


def main() -> int:
    res = build()
    print(f"built site/: {res['pages']} pages, {res['charts']} charts, {res['datasets']} datasets (share_exec, approved aggregates, whitelisted evaluation summaries, governance metadata)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
