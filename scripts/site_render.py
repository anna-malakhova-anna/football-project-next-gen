"""Plain labels, cell formatting, tables and the chart block of the results site.

Split out of scripts/build_site.py without changing a line. Values are relabelled in the exported rows so that charts and tables agree.
"""
from __future__ import annotations

import decimal
import html
import json

from scripts import site_cards, site_global as G, site_phase5 as P5


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
    "fan_vs_truth": {"estimator": {"NAIVE_EXISTING": "Naive comparison (existing fans)", "NAIVE": "Naive, all linked accounts (analyst detail)", "DID_ADDITIVE": "Matched before/after"}},
    "fan_effect": {"estimator": {"NAIVE_EXISTING": "Naive comparison (existing fans)", "NAIVE": "Naive, all linked accounts (analyst detail)", "DID_ADDITIVE": "Matched before/after"}},
    "uplift_events": {"uplift_status_group": {"ALL": "All linked households", "EXISTING": "Existing fans", "LAPSED": "Lapsed fans"}},
    "uplift_spend": {"uplift_status_group": {"ALL": "All linked households", "EXISTING": "Existing fans", "LAPSED": "Lapsed fans"}},
    "consent_by_capture_point": {"capture_point": {"checkout": "Checkout", "flag_registration": "Flag registration", "preference_center": "Preference center", "signup": "Sign-up"},
                                 "channel": {"email": "Email", "sms": "SMS", "push": "Push"}},
    "suppression_example": {"sex": {"F": "Female", "M": "Male", "U": "Unknown"}, "suppressed": {"NONE": "shown", "PRIMARY": "hidden: count below 10", "SECONDARY": "hidden: protects a hidden cell"}},
    "link_rate": {"country_code": {"ALL": "All countries"}},
    "restatement_log": {"likely_cause": {"SOURCE_REGISTRY_CHANGE": "A source was added to the registry", "NEW_SOURCE_DATA": "New or late source files",
                                          "IDENTITY_CHANGE": "Different identity matches", "METHODOLOGY_CHANGE": "Method changed", "DEFINITION_CHANGED": "Definition changed",
                                          "NEW_KPI": "New measure", "UNKNOWN": "Not explained"}},
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
    "years_since_launch": "Years since launch", "truth": "Truth", "source_system": "Source", "component": "Component", "component_label": "Source of doubt", "contract_version": "Contract version", "pass": "Passed", "warn": "Warnings",
    "error": "Errors", "onboarding_status": "Onboarding status", "description": "Description", "audience": "Audience", "share_tables": "Share tables", "columns_allowed": "Columns allowed",
    "columns_denied": "Columns denied", "kpi_rows": "KPI rows", "kpis": "KPIs", "restatement_required": "Restatements required", "step": "Step", "conversion": "Conversion", "conversion_base": "Share of",
    "true_survival": "True",
}
COLUMN_LABELS.update(P5.COLUMN_LABELS)
COLUMN_LABELS.update({k: v for k, v in G.COLUMN_LABELS.items() if k not in COLUMN_LABELS})
VALUE_LABELS.update(P5.VALUE_LABELS)
ID_COLUMNS = {"participation_year", "entry_year", "years_since_entry", "years_since_launch", "months_since_event", "months_since_origin", "horizon_months", "step"}
RATE_COLUMNS = P5.RATE_COLUMNS | {"girls_share_of_youth", "km_survival", "km_survival_ci_low", "km_survival_ci_high", "cohort_retention_pct", "cohort_retention_among_eligible_pct", "household_link_rate",
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
    if isinstance(v, decimal.Decimal) and v == v.to_integral_value():      # exact money sums come back as decimals: whole amounts read as counts
        v = int(v)
    if col in RATE_COLUMNS or col.endswith("_pct"):
        if isinstance(v, (int, float)) and abs(v) <= 5:
            return f"{v:.1%}"
    if isinstance(v, float):
        return f"{v:.4f}" if abs(v) < 10 else f"{v:,.1f}"
    if isinstance(v, int):
        return f"{v:,}" if col not in ID_COLUMNS else str(v)
    return str(v)


# columns that are in the exported file but not shown in the page table (a code beside its plain label, a sort key)
TABLE_HIDE = {"unc_decomp": {"component", "component_order"}}
PRODUCT_TABLES = {"conv_tier", "goal_scorecard", "product_health", "product_targets", "roadmap"}
RATIO_COLUMNS = {"value", "value_low", "value_high", "trust_value"}


def fmt_cell_product(v, col: str, row: dict) -> str:
    """Data product tab tables: no long decimals. A share of registered households and a ratio-unit KPI show as whole percents; any other fraction below 10 shows two decimals."""
    if isinstance(v, float) and not isinstance(v, bool):
        if col == "share_of_registered" or (col in RATIO_COLUMNS and row.get("trust_unit" if col == "trust_value" else "unit") == "ratio"):
            return f"{v:.0%}"
        if abs(v) < 10:
            return f"{v:.2f}"
    return fmt_cell(v, col)


def table_html(ds: dict, limit: int = 60) -> str:
    cols, rows = ds["columns"], ds["rows"][:limit]
    cell = (lambda r, c: fmt_cell_product(r[c], c, r)) if ds["name"] in PRODUCT_TABLES else (lambda r, c: fmt_cell(r[c], c))
    if not rows:
        return f"<p class='note'><b>No rows.</b> The query returned nothing, which is the expected result when {esc(ds['title'].lower())} has nothing to report.</p>"
    cols = [c for c in cols if c not in TABLE_HIDE.get(ds["name"], ())]
    head = "".join(f"<th>{esc(COLUMN_LABELS.get(c, c))}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{esc(cell(r, c))}</td>" for c in cols) + "</tr>" for r in rows)
    more = f"<p class='note'>First {limit} of {len(ds['rows'])} rows; the full file is data/{ds['name']}.json.</p>" if len(ds["rows"]) > limit else ""
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>{more}"


def chart_block(cid: str, ch: dict, data: dict) -> str:
    if ch.get("card"):
        return site_cards.card_block(cid, ch, data, table_html)
    tag = '<span class="tag">Synthetic evaluation \u2014 not observable in production</span>' if ch.get("evaluation") else ""
    tables = "".join(f"<p class='note'><b>{esc(data[n]['title'])}</b> <code>{esc(data[n]['source'])}</code></p>{table_html(data[n])}" for n in ch["datasets"])
    plot = ch["render"](data) if ch.get("render") else f'<div id="{cid}" role="img" aria-label="{esc(ch["title"])}"></div>'
    script = f'<script type="application/json" data-chart="{cid}">{json.dumps(ch["spec"])}</script>' if ch.get("spec") else ""
    decision = f'<p class="note"><b>Design choice.</b> {esc(ch["decision"])}</p>' if ch.get("decision") else ""
    note = f'<p class="note"><b>Reading note.</b> {esc(ch["note"](data))}</p>' if ch.get("note") else ""
    question = f'<p class="note question"><b>Question it answers.</b> {esc(ch["question"])}</p>' if ch.get("question") else ""
    lens = ""
    if ch.get("lens"):
        lens = ('<div class="lens-notes">' + f'<p class="note lens lens-club"><b>Club lens.</b> {esc(ch["lens"]["club"])}</p>'
                + f'<p class="note lens lens-privacy"><b>Privacy lens.</b> {esc(ch["lens"]["privacy"])}</p></div>')
    return (f'<section class="chart" id="sec-{cid}"><h3>{esc(ch["title"])}{tag}</h3>{question}{plot}'
            f'<p class="note"><b>What this shows.</b> {esc(ch["shows"])}</p>{decision}<p class="note"><b>What it does not show.</b> {esc(ch["doesnt"])}</p>{lens}{note}'
            f'<details><summary>The numbers behind this chart</summary>{tables}</details>'
            f'{script}</section>')


# The project's own mark: an American football with white laces on turf green, drawn here (no third-party mark). One source for the top bar and the favicon.
MARK = ('<rect width="32" height="32" rx="6" fill="#2F6B4F"/><g transform="rotate(-35 16 16)">'
        '<path d="M3.5 16C8 8 24 8 28.5 16C24 24 8 24 3.5 16Z" fill="#8A4B2A" stroke="#5E3119" stroke-width=".8"/>'
        '<path d="M8.6 13.3v5.4M23.4 13.3v5.4" stroke="#FFFFFF" stroke-width="1.2" stroke-linecap="round"/>'
        '<path d="M11.5 16h9M13 14.4v3.2M15 14.4v3.2M17 14.4v3.2M19 14.4v3.2" stroke="#FFFFFF" stroke-width="1.1" stroke-linecap="round"/></g>')
FAVICON = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">{MARK}</svg>'
