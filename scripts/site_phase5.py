"""Phase 5 additions to the results site (spec section 12): Data Quality, How Sure Are We, Club Markets and Privacy by Design pages.

Imported by scripts/build_site.py. The same rules apply as everywhere on the site: every number comes from a registered dataset (a share_club or share_privacy table, an approved aggregate, a whitelisted
evaluation summary or governance metadata), exported to site/data/<name>.json; a chart spec only maps fields to marks; stacking, ranking and rates are computed in SQL. Counts that passed small-cell suppression
show as "<k", never blank. All data is SYNTHETIC; the markets are a project approximation (ADR-016).
"""
from __future__ import annotations

SHARE_PREFIXES = ("share_exec.", "share_club.", "share_privacy.")
APPROVED = {
    "quality.dq_scorecard_source", "quality.dq_scorecard_org", "quality.dq_trend", "quality.mart_dq_impact", "quality.dq_fix_list",
    "quality.mart_uncertainty_decomposition", "quality.mart_missingness_bias",
}
EVAL = {"evaluation.eval_uncertainty_decomposition", "evaluation.eval_minimization_tradeoff", "demo_fix_list.scores", "demo_fix_list.nuance"}
GOVERNANCE = {"reference.privacy_params"}

GRADES = ["A", "B", "C", "D"]
GRADE_COLORS = ["#2166ac", "#92c5de", "#f4a582", "#b2182b"]          # blue to red: separable for the common colour-vision differences, and every cell also carries its letter
PURPOSES = ["COUNT", "SEGMENT", "GEO", "RETAIN", "ACTIVATE"]
K_MIN = "(select cast(value as integer) from reference.privacy_params where param = 'k_min')"
LATEST_Q = "(select max(season_year) from quality.dq_scorecard_source)"


def _D(name, sql, relations, kind, title):
    return {"name": name, "sql": sql.strip(), "relations": set(relations), "kind": kind, "title": title}


# state tile grid (column, row) for the 14 states that have a club market; each state cell holds up to four markets in a 2 x 2 block. A layout constant, not a number computed from data.
TILE = "(values ('WA',0,0),('CA',0,2),('AZ',1,3),('CO',2,2),('TX',3,4),('IL',4,1),('OH',5,1),('PA',6,1),('NY',6,0),('NJ',7,1),('CT',7,0),('MA',8,0),('GA',5,3),('FL',6,4)) t(state, c, r)"

DATASETS = [
    _D("dq_heatmap", f"""
        select source_system, purpose, dimension, grade, score, score_interval_low, score_interval_high, record_count
        from quality.dq_scorecard_source
        where season_year = {LATEST_Q} and score is not null and dimension in ('COMPLETENESS','VALIDITY','UNIQUENESS','CONSISTENCY','CONFORMITY','TIMELINESS','CONSENT_PROVENANCE','PURPOSE_SCORE')
        order by purpose, source_system, dimension""", ["quality.dq_scorecard_source"], "approved_aggregate", "Data quality grade by source, dimension and purpose, latest season"),
    _D("dq_control", """
        select entity_id as source_system, season_year, purpose, score, lcl, ucl, out_of_control, coalesce(direction, '') as direction
        from quality.dq_trend
        where entity_type = 'SOURCE' and entity_id in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') and purpose in ('COUNT', 'SEGMENT', 'ACTIVATE')
        order by purpose, entity_id, season_year""", ["quality.dq_trend"], "approved_aggregate", "Source quality scores with control limits"),
    _D("dq_pareto", f"""
        select purpose, rule_id, rank_in_purpose, impact_units, unit, cumulative_share
        from quality.mart_dq_impact
        where season_year = {LATEST_Q} and population = 'MODELLED' and purpose in ('COUNT', 'SEGMENT', 'RETAIN', 'ACTIVATE') and rank_in_purpose <= 6
        order by purpose, rank_in_purpose""", ["quality.mart_dq_impact", "quality.dq_scorecard_source"], "approved_aggregate", "Rules ranked by the participants (or households) they cost, latest season"),
    _D("dq_org_scatter", f"""
        select channel, record_count, score, score_interval_low, score_interval_high, interval_applied, grade
        from quality.dq_scorecard_org
        where season_year = {LATEST_Q} and purpose = 'SEGMENT' and dimension = 'PURPOSE_SCORE' and reported and source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED')
        order by record_count""", ["quality.dq_scorecard_org", "quality.dq_scorecard_source"], "approved_aggregate", "Organization quality score against organization size, latest season"),
    _D("dq_fix_card", f"""
        with pick as (
            select source_system, org_id from quality.dq_fix_list
            where season_year = {LATEST_Q} and not is_systemic and rank_in_scope = 1 order by records_affected desc, org_id limit 1)
        select 'League A (pseudonymized)' as organization, f.rank_in_scope as rank, f.rule_id, f.fix_guidance, f.records_affected, f.impact_estimate, f.impact_unit, f.owner_role
        from quality.dq_fix_list f join pick p using (source_system, org_id)
        where f.season_year = {LATEST_Q} and not f.is_systemic order by f.rank_in_scope""", ["quality.dq_fix_list", "quality.dq_scorecard_source"], "approved_aggregate", "An example fix list (one organization, pseudonymized)"),
    _D("unc_decomp", """
        select participation_year, component, reported_point, interval_low, interval_high, contribution
        from quality.mart_uncertainty_decomposition order by participation_year, component""", ["quality.mart_uncertainty_decomposition"], "approved_aggregate",
       "Participants counted, with three separate uncertainty intervals"),
    _D("miss_dumbbell", f"""
        select participation_year, segment_value as division, value_known_only, bound_low, bound_high, unknown, total
        from quality.mart_missingness_bias
        where kpi = 'girls_share_of_youth' and club_market_id = 'ALL' and segment_value <> 'ALL' and total >= {K_MIN}
        order by participation_year, segment_value""", ["quality.mart_missingness_bias", "reference.privacy_params"], "approved_aggregate",
       "Girls' share of youth by division: known-only value and the bounds when unknown genders are assigned either way"),
    _D("unc_truth", """
        select participation_year, 'Identity' as component, identity_low as low, identity_high as high, true_participants_in_data as truth,
               identity_interval_contains_truth as truth_inside
        from evaluation.eval_uncertainty_decomposition
        union all
        select participation_year, 'Data-quality exclusions', dq_strict, dq_lenient, true_participants_in_data, true_participants_in_data between dq_strict and dq_lenient
        from evaluation.eval_uncertainty_decomposition
        union all
        select participation_year, 'Coverage (total incl. dark organizations)', identity_point + coverage_low, identity_point + coverage_high, true_total_participants,
               true_total_participants between identity_point + coverage_low and identity_point + coverage_high
        from evaluation.eval_uncertainty_decomposition
        order by 1, 2""", ["evaluation.eval_uncertainty_decomposition"], "evaluation", "Each uncertainty component against the synthetic truth"),
    _D("fix_demo_scores", "select org_group, purpose, orgs_scored, score_before, score_after from demo_fix_list.scores order by org_group, purpose", ["demo_fix_list.scores"], "evaluation",
       "SIMULATED: purpose scores of organizations that acted on a fix list, before and after"),
    _D("fix_demo_nuance", "select measure, value_before, value_after from demo_fix_list.nuance order by measure", ["demo_fix_list.nuance"], "evaluation",
       "SIMULATED: what the fix list does to the nuance layer"),
    # ---- club markets (share_club only) ----
    _D("market_tiles", f"""
        with latest as (select max(participation_year) as y from share_club.share_club__market_year),
        m as (
            select club_market_id, participation_year, participants_allocated, participants_allocated_interval_low as lo, participants_allocated_interval_high as hi,
                   grade_count, grade_segment, grade_geo, grade_retain, grade_activate, suppressed,
                   substr(club_market_id, 4, 2) as state, cast(right(club_market_id, 2) as integer) as n
            from share_club.share_club__market_year, latest where regexp_matches(club_market_id, '^CM-') and participation_year = latest.y),
        tiles as (
            select m.*, 2 * t.c + ((n - 1) % 2) as x, 2 * t.r + ((n - 1) // 2) as y from m join {TILE} on t.state = m.state),
        long as (
            select club_market_id, x, y, 1 as k, 'COUNT' as purpose, grade_count as grade, suppressed, participants_allocated, lo, hi from tiles
            union all select club_market_id, x, y, 2, 'SEGMENT', grade_segment, suppressed, participants_allocated, lo, hi from tiles
            union all select club_market_id, x, y, 3, 'GEO', grade_geo, suppressed, participants_allocated, lo, hi from tiles
            union all select club_market_id, x, y, 4, 'RETAIN', grade_retain, suppressed, participants_allocated, lo, hi from tiles
            union all select club_market_id, x, y, 5, 'ACTIVATE', grade_activate, suppressed, participants_allocated, lo, hi from tiles)
        select club_market_id, x, y, purpose, grade, suppressed,
               case when suppressed = 'NONE' then cast(round(participants_allocated) as varchar) else '<k' end as participants_label,
               case when suppressed = 'NONE' and hi > 0 then round(100.0 * participants_allocated / ((lo + hi) / 2)) end as coverage_pct
        from long
        order by k, club_market_id""", ["share_club.share_club__market_year"], "share_club", "Club-market tile map: grade for each purpose, participants and coverage"),
    _D("market_series", """
        select club_market_id, participation_year, participants_allocated, participants_allocated_interval_low as interval_low, participants_allocated_interval_high as interval_high, suppressed
        from share_club.share_club__market_year where regexp_matches(club_market_id, '^CM-') and suppressed = 'NONE' order by club_market_id, participation_year""",
       ["share_club.share_club__market_year"], "share_club", "Participants per club market and year, with the coverage interval"),
    _D("market_funnel", """
        with latest as (select max(participation_year) as y from share_club.share_club__activation_funnel),
        f as (
            select step_no, step, unit, funnel_count as remaining, funnel_lost_dq as lost_dq, funnel_lost_privacy as lost_privacy
            from share_club.share_club__activation_funnel, latest where participation_year = latest.y and club_market_id = 'ALL')
        select step_no, step, unit, 'Lost to data quality' as loss, 0 as x0, lost_dq as x1, remaining from f where step_no > 1
        union all
        select step_no, step, unit, 'Lost to privacy (consent)', lost_dq, lost_dq + lost_privacy, remaining from f where step_no > 1
        order by step_no, loss""", ["share_club.share_club__activation_funnel"], "share_club", "Where families are lost between registration and a reachable guardian, by cause (all markets)"),
    _D("market_orgs", """
        select club_market_id, 'Reporting organizations' as kind, 0 as x0, orgs_reporting as x1
        from share_club.share_club__market_year where regexp_matches(club_market_id, '^CM-') and suppressed = 'NONE'
          and participation_year = (select max(participation_year) from share_club.share_club__market_year)
        union all
        select club_market_id, 'Dark organizations (sent no file)', orgs_reporting, orgs_reporting + orgs_dark
        from share_club.share_club__market_year where regexp_matches(club_market_id, '^CM-') and suppressed = 'NONE'
          and participation_year = (select max(participation_year) from share_club.share_club__market_year)
        order by 1, 2""", ["share_club.share_club__market_year"], "share_club", "Known organizations per club market: reporting and dark, latest season"),
    _D("lens_club", """
        select club_market_id, market_name, participation_year, participants_allocated, participants_allocated_interval_low, participants_allocated_interval_high, orgs_known, orgs_dark,
               grade_count, grade_segment, grade_geo, grade_retain, grade_activate
        from share_club.share_club__market_year
        where club_market_id = (select club_market_id from share_club.share_club__market_year where regexp_matches(club_market_id, '^CM-') and suppressed = 'NONE'
                                and participation_year = (select max(participation_year) from share_club.share_club__market_year) order by participants_allocated desc, club_market_id limit 1)
          and suppressed = 'NONE' order by participation_year""", ["share_club.share_club__market_year"], "share_club", "The largest market in the club lens: participants, coverage and grades by year"),
    _D("lens_privacy", """
        select f.club_market_id, f.step_no, f.step, f.unit, f.funnel_count, f.funnel_lost_dq, f.funnel_lost_privacy, f.suppressed
        from share_club.share_club__activation_funnel f
        where f.club_market_id = (select club_market_id from share_club.share_club__market_year where regexp_matches(club_market_id, '^CM-') and suppressed = 'NONE'
                                  and participation_year = (select max(participation_year) from share_club.share_club__market_year) order by participants_allocated desc, club_market_id limit 1)
          and f.participation_year = (select max(participation_year) from share_club.share_club__activation_funnel) order by f.step_no""",
       ["share_club.share_club__activation_funnel", "share_club.share_club__market_year"], "share_club", "The same market in the privacy lens: the activation funnel and what each loss is"),
    # ---- privacy ----
    _D("frontier", """
        select variant_id, label as variant_label, in_standard, pct_unique, pct_rows_below_k_min, precision, recall, f1, sibling_or_twin_false_merges, participant_count_error_pct, fit_for_activate, contact_fields_held
        from evaluation.eval_minimization_tradeoff where is_headline_matcher and precision is not null order by variant_id""",
       ["evaluation.eval_minimization_tradeoff"], "evaluation", "Minimization frontier: re-identification risk against identity accuracy, one point per variant"),
    _D("consent_prov", """
        with latest as (select max(participation_year) as y from share_privacy.share_privacy__consent_provenance where source_system is not null),
        c as (
            select source_system, consent_text_version, provenance_grade, consent_events, suppressed
            from share_privacy.share_privacy__consent_provenance, latest where participation_year = latest.y and source_system is not null),
        s as (
            select *, coalesce(sum(consent_events) over (partition by source_system, consent_text_version order by provenance_grade rows between unbounded preceding and 1 preceding), 0) as x0
            from c)
        select source_system, consent_text_version, provenance_grade, consent_events, suppressed, x0, x0 + coalesce(consent_events, 0) as x1,
               source_system || ' / ' || consent_text_version as form
        from s order by source_system, consent_text_version, provenance_grade""", ["share_privacy.share_privacy__consent_provenance"], "share_privacy",
       "Consent events by provenance grade, source and consent text version, latest season"),
    _D("purpose_matrix", "select consent_text_version, purpose, purpose_label, form_names_purpose, separate_consent_required, "
       "case when form_names_purpose then 'Named on the form' else 'Not named' end as coverage, case when form_names_purpose then 'yes' else 'no' end as mark "
       "from share_privacy.share_privacy__purpose_coverage order by consent_text_version, purpose",
       ["share_privacy.share_privacy__purpose_coverage"], "share_privacy", "Which purposes each consent wording names"),
    _D("retention_del", """
        select metric_label, 'Rebuilt from anonymized facts' as scenario, coalesce(facts_only_change, 0) as change, survives_facts_only as survives from share_privacy.share_privacy__retention_vs_deletion
        where baseline > 0
        union all
        select metric_label, 'Identity re-run on anonymized inputs', coalesce(identity_rebuilt_change, 0), survives_identity_rebuilt from share_privacy.share_privacy__retention_vs_deletion where baseline > 0
        order by 1, 2""", ["share_privacy.share_privacy__retention_vs_deletion"], "share_privacy", "Change in each retention figure after the age-out deletion"),
    _D("analyst_k", "select participation_year, participant_years, equivalence_classes, smallest_class, average_class_size, pct_unique, pct_rows_below_k_warn, pct_rows_below_k_min "
       "from share_privacy.share_privacy__analyst_k_anonymity order by 1", ["share_privacy.share_privacy__analyst_k_anonymity"], "share_privacy", "How identifying the analyst share is, per year"),
    _D("policy_results", "select check_name, violations from share_privacy.share_privacy__policy_checks order by 1", ["share_privacy.share_privacy__policy_checks"], "share_privacy", "Share-policy check results"),
]

VALUE_LABELS = {
    "dq_heatmap": {"source_system": {"US_LEAGUE": "US league", "CA_CLUB": "Canadian club", "INTL_FED": "International federation", "SCHOOL_AGGREGATES": "School programs", "FAN_ENGAGEMENT": "Fan app and ticketing"}},
    "dq_control": {"source_system": {"US_LEAGUE": "US league", "CA_CLUB": "Canadian club", "INTL_FED": "International federation"}},
}

COLUMN_LABELS = {
    "source_system": "Source", "purpose": "Purpose", "dimension": "Dimension", "grade": "Grade", "score": "Score", "score_interval_low": "Interval, low", "score_interval_high": "Interval, high",
    "record_count": "Records", "season_year": "Season", "lcl": "Lower limit", "ucl": "Upper limit", "out_of_control": "Outside limits", "direction": "Direction", "rule_id": "Rule",
    "rank_in_purpose": "Rank", "impact_units": "Cost", "unit": "Unit", "cumulative_share": "Cumulative share", "channel": "Channel", "interval_applied": "Interval applied", "organization": "Organization",
    "rank": "Fix", "fix_guidance": "What to do", "records_affected": "Records affected", "impact_estimate": "Estimated cost", "impact_unit": "Cost unit", "owner_role": "Owner",
    "component": "Component", "reported_point": "Counted", "interval_low": "Interval, low", "interval_high": "Interval, high", "contribution": "Width", "division": "Division",
    "value_known_only": "Known only", "bound_low": "Lower bound", "bound_high": "Upper bound", "unknown": "Unknown gender", "total": "Youth", "low": "Low", "high": "High", "truth": "Truth", "truth_inside": "Truth inside",
    "org_group": "Group", "orgs_scored": "Organizations", "score_before": "Before", "score_after": "After", "measure": "Measure", "value_before": "Before", "value_after": "After",
    "club_market_id": "Club market", "x": "Column", "y": "Row", "participants_label": "Participants", "coverage_pct": "Coverage %", "suppressed": "Status", "participants_allocated": "Participants (allocated)",
    "step_no": "Step no.", "step": "Step", "loss": "Loss", "x0": "From", "x1": "To", "remaining": "Remaining", "markets_shown": "Markets shown", "markets": "Markets", "kind": "Kind",
    "market_name": "Market", "participants_allocated_interval_low": "Interval, low", "participants_allocated_interval_high": "Interval, high", "orgs_known": "Known organizations", "orgs_dark": "Dark organizations",
    "grade_count": "Count", "grade_segment": "Segment", "grade_geo": "Geography", "grade_retain": "Retention", "grade_activate": "Activation", "funnel_count": "Remaining", "funnel_lost_dq": "Lost: data quality",
    "funnel_lost_privacy": "Lost: privacy", "variant_id": "Variant", "variant_label": "Variant", "pct_unique": "Unique (%)", "pct_rows_below_k_min": "In a class below k_min (%)", "precision": "Precision", "recall": "Recall",
    "f1": "F1", "sibling_or_twin_false_merges": "Sibling or twin false merges", "participant_count_error_pct": "Count error (%)", "fit_for_activate": "Fit for activation", "contact_fields_held": "Contact fields held",
    "consent_text_version": "Consent wording", "provenance_grade": "Provenance", "consent_events": "Consent events", "form": "Form", "purpose_label": "Purpose", "form_names_purpose": "Named on form",
    "separate_consent_required": "Needs its own consent", "coverage": "Coverage", "mark": "Named", "metric_label": "Figure", "scenario": "Scenario", "change": "Change", "survives": "Within tolerance",
    "participation_year": "Year", "participant_years": "Participant-years", "equivalence_classes": "Classes", "smallest_class": "Smallest class", "average_class_size": "Average class size",
    "pct_rows_below_k_warn": "Below warning size (%)", "check_name": "Check", "violations": "Violations", "participants_allocated_label": "Participants",
}
RATE_COLUMNS = {"cumulative_share", "change", "value_known_only", "bound_low", "bound_high", "precision", "recall", "f1", "fit_for_activate"}


# ------------------------------------------------------------------ charts
def _src(name):
    return {"url": f"data/{name}.json", "format": {"type": "json", "property": "rows"}}


GRADE_SCALE = {"domain": GRADES, "range": GRADE_COLORS}
NOT_SUPPRESSED_NOTE = "A cell shown as <k has fewer than k_min records behind it and is hidden, never shown as blank."


def charts():
    """-> {id: dict(page, title, spec|render, shows, doesnt, question, lens, datasets, ...)} for the four Phase 5 pages."""
    C = {}
    C["q1_heatmap"] = dict(
        page="quality", title="Which data can I trust, for what? (grade by source, dimension and purpose)", datasets=["dq_heatmap"],
        question="Which data can I trust, for what? (asked by clubs and by the privacy lead)",
        spec={"data": _src("dq_heatmap"), "facet": {"field": "purpose", "type": "nominal", "sort": PURPOSES, "columns": 2, "title": None},
              "spec": {"width": 330, "height": 150, "layer": [
                  {"mark": "rect", "encoding": {
                      "x": {"field": "dimension", "type": "nominal", "title": None, "axis": {"labelAngle": -40}, "sort": ["COMPLETENESS", "VALIDITY", "UNIQUENESS", "CONSISTENCY", "CONFORMITY", "TIMELINESS", "CONSENT_PROVENANCE", "PURPOSE_SCORE"]},
                      "y": {"field": "source_system", "type": "nominal", "title": None},
                      "color": {"field": "grade", "type": "nominal", "scale": GRADE_SCALE, "legend": {"title": "Grade"}},
                      "tooltip": [{"field": "source_system"}, {"field": "dimension"}, {"field": "grade"}, {"field": "score"}, {"field": "score_interval_low"}, {"field": "score_interval_high"}, {"field": "record_count"}]}},
                  {"mark": {"type": "text", "fontSize": 11}, "encoding": {"x": {"field": "dimension", "type": "nominal", "sort": ["COMPLETENESS", "VALIDITY", "UNIQUENESS", "CONSISTENCY", "CONFORMITY", "TIMELINESS", "CONSENT_PROVENANCE", "PURPOSE_SCORE"]}, "y": {"field": "source_system", "type": "nominal"},
                      "text": {"field": "grade", "type": "nominal"}, "color": {"value": "#000000"}}}]}},
        shows="One panel per purpose, one cell per source and quality dimension, each with its grade as a colour and as a letter. The same sources earn different grades for different purposes, because a rule only counts against the purposes that need it.",
        doesnt="A verdict on any organization, or real data quality: the data is synthetic. A grade rests on the rules in the registry, and a small source carries a wide interval (shown when you hover; the grade uses its lower bound).",
        lens=dict(club="Read across a row: a source can be good enough to count and still poor for contacting families.", privacy="The ACTIVATE panel is the privacy panel: consent provenance, not typing errors, holds the grade down."))
    C["q2_control"] = dict(
        page="quality", title="Is quality getting better or worse, and is this a real shift? (control limits per source)", datasets=["dq_control"],
        question="Is quality getting better or worse, and is this a real shift? (clubs and analytics)",
        spec={"data": _src("dq_control"), "facet": {"field": "purpose", "type": "nominal", "sort": ["COUNT", "SEGMENT", "ACTIVATE"], "columns": 3, "title": None},
              "spec": {"width": 230, "height": 200, "layer": [
                  {"mark": {"type": "area", "opacity": 0.12}, "encoding": {"x": {"field": "season_year", "type": "ordinal", "title": "Season", "axis": {"labelAngle": 0}},
                      "y": {"field": "lcl", "type": "quantitative", "scale": {"domain": [0, 100]}, "title": "Score"}, "y2": {"field": "ucl"}, "color": {"field": "source_system", "type": "nominal", "title": "Source"}}},
                  {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "season_year", "type": "ordinal"}, "y": {"field": "score", "type": "quantitative"},
                      "color": {"field": "source_system", "type": "nominal", "title": "Source"}}},
                  {"mark": {"type": "point", "shape": "diamond", "size": 160, "filled": False, "strokeWidth": 2.5}, "encoding": {"x": {"field": "season_year", "type": "ordinal"},
                      "y": {"field": "score", "type": "quantitative"}, "stroke": {"field": "out_of_control", "type": "nominal", "scale": {"domain": [True, False], "range": ["#000000", "rgba(0,0,0,0)"]}, "legend": None},
                      "tooltip": [{"field": "source_system"}, {"field": "season_year"}, {"field": "score"}, {"field": "direction"}]}}]}},
        shows="A source's score each season against the limits that its own earlier seasons imply (a P-chart); a diamond marks a season outside them, and the tooltip says which way.",
        doesnt="Why a score moved. A point outside the limits says the change is bigger than the season-to-season noise, not what caused it. The first season has no limits, and the limits are wide while a source has few seasons.",
        lens=dict(club="A move outside the limits is worth a question to the source; a move inside is noise.", privacy="Consent provenance moves slowly because forms change slowly; a sudden move means a form changed."))
    C["q3_pareto"] = dict(
        page="quality", title="Which few fixes matter most? (rules ranked by what they cost)", datasets=["dq_pareto"],
        question="Which few fixes matter most? (clubs and the privacy lead)",
        spec={"data": _src("dq_pareto"), "facet": {"field": "purpose", "type": "nominal", "sort": ["COUNT", "SEGMENT", "RETAIN", "ACTIVATE"], "columns": 2, "title": None},
              "spec": {"width": 300, "height": 190, "layer": [
                  {"mark": "bar", "encoding": {"x": {"field": "rule_id", "type": "nominal", "sort": {"field": "rank_in_purpose", "op": "min"}, "title": None, "axis": {"labelAngle": -50, "labelLimit": 220}},
                      "y": {"field": "impact_units", "type": "quantitative", "title": "Participants (households for ACTIVATE)"}, "color": {"value": "#3D7CC9"}}},
                  {"mark": {"type": "line", "point": True, "color": "#D9622B"}, "encoding": {"x": {"field": "rule_id", "type": "nominal", "sort": {"field": "rank_in_purpose", "op": "min"}},
                      "y": {"field": "cumulative_share", "type": "quantitative", "axis": {"format": "%", "title": "Cumulative share"}, "scale": {"domain": [0, 1]}}}}]},
              "resolve": {"scale": {"y": "independent"}}},
        shows="For each purpose, the rules ranked by how many participants (or, for activation, households) their failures remove, with the cumulative share on the second axis. A handful of rules account for most of the cost.",
        doesnt="Savings. The cost is what failing records remove from a count, not what a fix would recover; and the same participant can be hit by several rules, so the bars are not additive across rules.",
        lens=dict(club="Fix the first bar of your purpose first.", privacy="For activation, the top rules are consent-provenance rules: fixing them means changing a form, not cleaning data."))
    C["q4_scatter"] = dict(
        page="quality", title="Is it small leagues, a channel, or everyone? (organization score against size)", datasets=["dq_org_scatter"],
        question="Is it small leagues, a channel, or everyone? (clubs)",
        spec={"data": _src("dq_org_scatter"), "width": "container", "height": 340, "layer": [
            {"mark": {"type": "rule", "opacity": 0.35}, "encoding": {"x": {"field": "record_count", "type": "quantitative", "scale": {"type": "log"}, "title": "Registrations in the season (log scale)"},
                "y": {"field": "score_interval_low", "type": "quantitative", "scale": {"domain": [0, 100]}, "title": "Segmentation purpose score"}, "y2": {"field": "score_interval_high"},
                "color": {"field": "channel", "type": "nominal", "title": "Channel"}}},
            {"mark": {"type": "point", "filled": True, "size": 60}, "encoding": {"x": {"field": "record_count", "type": "quantitative", "scale": {"type": "log"}},
                "y": {"field": "score", "type": "quantitative"}, "color": {"field": "channel", "type": "nominal"}, "tooltip": [{"field": "grade"}, {"field": "record_count"}, {"field": "score"}, {"field": "channel"}]}}]},
        shows="Each point is an organization's segmentation score for the latest season; the vertical bar is its interval, which is wide for small organizations and shrinks with size.",
        doesnt="Which organization is which: the points carry no names. It also does not show cause: small organizations and the spreadsheet channel overlap.",
        lens=dict(club="If your league is small, read your interval before your grade.", privacy="Small organizations also carry the highest re-identification risk when their data is shared."))
    C["q5_fixcard"] = dict(
        page="quality", title="What do we actually ask an operator to do? (a fix list)", datasets=["dq_fix_card"],
        question="What do we actually ask an operator to do? (clubs and the privacy lead)",
        render=lambda d: render_fix_card(d["dq_fix_card"]["rows"]),
        shows="The top fixes for one organization, worded as actions with the number of records each affects, who owns it, and the estimated cost in participants or households.",
        doesnt="Any real organization: this one is pseudonymized and synthetic. Records are counted, never listed, so the card carries nothing about a person.",
        lens=dict(club="This is the page a league operator would receive.", privacy="The card names records by count only; the operator sees their own rows in their own system."))
    # ---- How sure are we ----
    C["u1_decomp"] = dict(
        page="sure", title="Why can't you give me one number, and what drives the range? (three separate intervals)", datasets=["unc_decomp"],
        question="Why can't you give me one number, and what drives the range? (executives and clubs)",
        spec={"data": _src("unc_decomp"), "facet": {"field": "participation_year", "type": "ordinal", "columns": 5, "title": None},
              "spec": {"width": 150, "height": 170, "layer": [
                  {"mark": {"type": "rule", "strokeWidth": 7, "opacity": 0.55}, "encoding": {"y": {"field": "component", "type": "nominal", "title": None, "sort": ["IDENTITY", "DQ_EXCLUSIONS", "COVERAGE"]},
                      "x": {"field": "interval_low", "type": "quantitative", "scale": {"zero": False}, "title": "Participants"}, "x2": {"field": "interval_high"}, "color": {"field": "component", "type": "nominal", "legend": None}}},
                  {"mark": {"type": "tick", "color": "#000000", "thickness": 2, "size": 18}, "encoding": {"y": {"field": "component", "type": "nominal", "sort": ["IDENTITY", "DQ_EXCLUSIONS", "COVERAGE"]},
                      "x": {"field": "reported_point", "type": "quantitative"}}}]}},
        shows="For each year, the participant count (tick) with three separate bars: what identity resolution could move it by, what dropping records that fail the counting rules would remove, and what organizations that sent no file might add.",
        doesnt="One overall interval, on purpose: the three are not independent and coverage is an estimate, not a bound, so they are never added together (ADR-015).",
        lens=dict(club="The coverage bar is the one clubs can act on: it is the organizations that did not report.", privacy="The identity bar is the one with a privacy edge: wrongly merged siblings sit in it."))
    C["u2_missing"] = dict(
        page="sure", title="Is the girls' trend real, or an artefact of missing data? (known-only value and bounds)", datasets=["miss_dumbbell"],
        question="Is the girls' trend real, or an artefact of missing data? (clubs and the privacy lead)",
        spec={"data": _src("miss_dumbbell"), "facet": {"field": "participation_year", "type": "ordinal", "columns": 5, "title": None},
              "spec": {"width": 150, "height": 190, "layer": [
                  {"mark": {"type": "rule", "strokeWidth": 4, "opacity": 0.6}, "encoding": {"y": {"field": "division", "type": "nominal", "title": None},
                      "x": {"field": "bound_low", "type": "quantitative", "scale": {"zero": False}, "axis": {"format": "%", "title": "Girls' share"}}, "x2": {"field": "bound_high"}}},
                  {"mark": {"type": "point", "filled": True, "color": "#D9622B", "size": 60}, "encoding": {"y": {"field": "division", "type": "nominal"},
                      "x": {"field": "value_known_only", "type": "quantitative"}, "tooltip": [{"field": "division"}, {"field": "unknown"}, {"field": "total"}]}}]}},
        shows="By division and year, the girls' share among children whose gender is known (dot) and the range it would span if every unknown were a girl or a boy (bar). Missing gender is concentrated in the youngest divisions and in spreadsheet files.",
        doesnt="The truth: the bar is a bound, not an estimate, and it narrows with fewer unknowns. Divisions with fewer than k_min children are left out. Nothing is imputed.",
        lens=dict(club="Compare divisions you coach: the bars are widest where gender is most often blank.", privacy="Gender is not collected on every form on purpose; the bar is what that choice costs the statistic."))
    C["u3_overlay"] = dict(
        page="sure", title="Do the methods work? (each component against the synthetic truth)", datasets=["unc_truth"], evaluation=True,
        question="Do the methods work? (technical reviewers)",
        spec={"data": _src("unc_truth"), "facet": {"field": "participation_year", "type": "ordinal", "columns": 5, "title": None},
              "spec": {"width": 150, "height": 150, "layer": [
                  {"mark": {"type": "rule", "strokeWidth": 7, "opacity": 0.5}, "encoding": {"y": {"field": "component", "type": "nominal", "title": None},
                      "x": {"field": "low", "type": "quantitative", "scale": {"zero": False}, "title": "Participants"}, "x2": {"field": "high"}, "color": {"field": "truth_inside", "type": "nominal",
                      "scale": {"domain": [True, False], "range": ["#2F6B4F", "#D9622B"]}, "legend": {"title": "Truth inside"}}}},
                  {"mark": {"type": "point", "shape": "cross", "color": "#000000", "size": 90, "strokeWidth": 2}, "encoding": {"y": {"field": "component", "type": "nominal"},
                      "x": {"field": "truth", "type": "quantitative"}}}]}},
        shows="Each component's interval with the true number (cross) from the generator's answer key. Identity and data-quality exclusions bracket the truth; the coverage interval does so in some years only.",
        doesnt="Performance on real data, where there is no answer key. The coverage estimate was not tuned after seeing these results, and its interval is too narrow in some years: that is reported, not hidden.",
        lens=dict(club="The coverage miss is why the club view shows a range, not a point.", privacy="Identity bounds covering the truth is the evidence that sibling merges are not hiding in the count."))
    C["u4_fixdemo"] = dict(
        page="sure", title="What's the payoff of fixing upstream? (SIMULATED fix-list adoption)", datasets=["fix_demo_scores", "fix_demo_nuance"], evaluation=True,
        question="What's the payoff of fixing upstream? (clubs and the privacy lead)",
        spec={"data": _src("fix_demo_scores"), "facet": {"field": "org_group", "type": "nominal", "columns": 2, "title": None},
              "spec": {"width": 260, "height": 190, "layer": [
                  {"mark": {"type": "rule", "strokeWidth": 3, "color": "#8A96A3"}, "encoding": {"y": {"field": "purpose", "type": "nominal", "sort": PURPOSES, "title": None},
                      "x": {"field": "score_before", "type": "quantitative", "scale": {"domain": [50, 100]}, "title": "Purpose score"}, "x2": {"field": "score_after"}}},
                  {"mark": {"type": "point", "filled": True, "color": "#8A96A3", "size": 70}, "encoding": {"y": {"field": "purpose", "type": "nominal", "sort": PURPOSES}, "x": {"field": "score_before", "type": "quantitative"}}},
                  {"mark": {"type": "point", "filled": True, "color": "#2F6B4F", "size": 70, "shape": "diamond"}, "encoding": {"y": {"field": "purpose", "type": "nominal", "sort": PURPOSES}, "x": {"field": "score_after", "type": "quantitative"}}}]}},
        shows="Purpose scores before (grey dot) and after (green diamond) half the struggling organizations act on their fix list in the final season, beside the struggling organizations that did not. The table shows what it does to the uncertainty.",
        doesnt="That any organization would act, or an effect size. It is a simulated scenario on synthetic data. It narrows the missingness bounds only slightly, because the large uncertainty is coverage, which a fix list does not touch.",
        lens=dict(club="Fixing upstream lifts your organization's scores; it does not close the coverage gap.", privacy="Better forms and fewer blanks improve quality without collecting more personal data."))
    # ---- Club markets ----
    C["m1_tiles"] = dict(
        page="markets", title="How's my market? (grade by purpose, participants and coverage)", datasets=["market_tiles"],
        question="How's my market? (clubs)",
        spec={"data": _src("market_tiles"), "facet": {"field": "purpose", "type": "nominal", "sort": PURPOSES, "columns": 3, "title": None},
              "spec": {"width": 230, "height": 150, "layer": [
                  {"mark": {"type": "rect", "stroke": "#ffffff", "strokeWidth": 1}, "encoding": {"x": {"field": "x", "type": "ordinal", "axis": None}, "y": {"field": "y", "type": "ordinal", "axis": None},
                      "color": {"field": "grade", "type": "nominal", "scale": GRADE_SCALE, "legend": {"title": "Grade"}},
                      "tooltip": [{"field": "club_market_id"}, {"field": "grade"}, {"field": "participants_label"}, {"field": "coverage_pct"}]}},
                  {"mark": {"type": "text", "fontSize": 9}, "encoding": {"x": {"field": "x", "type": "ordinal"}, "y": {"field": "y", "type": "ordinal"}, "text": {"field": "participants_label", "type": "nominal"},
                      "color": {"value": "#000000"}}}]}},
        note=lambda d: "Markets with no participants in the data are not drawn.",
        shows="Each tile is one club market, laid out roughly like a map of the states that have one (no boundaries are drawn). Colour and letter are the market's grade for the purpose in the panel; the label is the participants allocated to it.",
        doesnt="A club's territory: the markets are a project approximation made of ZIP3 groups (ADR-016). The labels are allocated, so a market that shares a ZIP3 holds a fraction of it. Cells below the small-cell size show as <k.",
        lens=dict(club="Find your tile in each panel: counted, but perhaps not reachable.", privacy="The same tile is not graded for sharing: grades say fitness for a purpose, not permission to use data for it."))
    C["m2_series"] = dict(
        page="markets", title="Is growth real or just better reporting? (participants and coverage band per market)", datasets=["market_series"],
        question="Is growth real or just better reporting? (clubs)",
        spec={"data": _src("market_series"), "facet": {"field": "club_market_id", "type": "nominal", "columns": 6, "title": None},
              "spec": {"width": 110, "height": 80, "layer": [
                  {"mark": {"type": "area", "opacity": 0.25}, "encoding": {"x": {"field": "participation_year", "type": "ordinal", "title": None, "axis": {"labelAngle": -90, "labelFontSize": 8}},
                      "y": {"field": "interval_low", "type": "quantitative", "title": None, "axis": {"labelFontSize": 8}}, "y2": {"field": "interval_high"}}},
                  {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "participation_year", "type": "ordinal"}, "y": {"field": "participants_allocated", "type": "quantitative"}}}]},
              "resolve": {"scale": {"y": "independent"}}},
        shows="For each market, allocated participants by year (line) with the band that allows for organizations that did not report that year. A rise inside a widening band is better reporting, not growth.",
        doesnt="Growth in the sport. The band is an estimate, markets launch in different years in this synthetic world, and each panel has its own vertical scale, so panels are not comparable by height.",
        lens=dict(club="Read the band before the line.", privacy="The same lines are what an unsuppressed small market would reveal: markets below the small-cell size are not drawn."))
    C["m3_funnel"] = dict(
        page="markets", title="Why can't I reach more families? (where families drop out, by cause)", datasets=["market_funnel"],
        question="Why can't I reach more families? (clubs, answered with the privacy lead)",
        spec={"data": _src("market_funnel"), "width": "container", "height": 260, "mark": {"type": "bar"},
              "encoding": {"y": {"field": "step", "type": "nominal", "sort": {"field": "step_no"}, "title": None},
                           "x": {"field": "x0", "type": "quantitative", "title": "Households lost at the step"}, "x2": {"field": "x1"},
                           "color": {"field": "loss", "type": "nominal", "scale": {"domain": ["Lost to data quality", "Lost to privacy (consent)"], "range": ["#D9622B", "#7D4E8E"]}, "title": "Cause"},
                           "tooltip": [{"field": "step"}, {"field": "loss"}, {"field": "remaining"}]},
              },
        shows="At each step from registration to a contactable guardian, the households lost because a record is missing or unusable (orange) and because consent was declined, revoked or never covered the purpose (purple). Nationally, all markets together.",
        doesnt="A choice about which to fix: the privacy losses are the family's decision and are not a defect. The national figures are shown; a single market's funnel is in the market lens below.",
        lens=dict(club="The orange bars are yours to fix with the league; the purple bars are the families' answer.", privacy="The purple bars are the privacy design working: a family that said no, or whose form never asked, is not contacted."))
    C["m4_orgs"] = dict(
        page="markets", title="How much of my market is dark? (known and reporting organizations)", datasets=["market_orgs"],
        question="How much of my market is dark? (clubs)",
        spec={"data": _src("market_orgs"), "width": "container", "height": 520, "mark": {"type": "bar"},
              "encoding": {"y": {"field": "club_market_id", "type": "nominal", "title": None}, "x": {"field": "x0", "type": "quantitative", "title": "Known organizations"}, "x2": {"field": "x1"},
                           "color": {"field": "kind", "type": "nominal", "scale": {"domain": ["Reporting organizations", "Dark organizations (sent no file)"], "range": ["#2F6B4F", "#B8A06A"]}, "title": None}}},
        shows="For each market, the organizations known to exist in the latest season: those that sent a file (green) and those that sent none (sand). The participants of a dark organization are in no source.",
        doesnt="The size of a dark organization: this counts organizations, not people. The people are estimated in the coverage band of the previous chart.",
        lens=dict(club="Dark organizations are where a call from the club helps most.", privacy="A dark organization sent nothing, so nothing about its families was ever held."))
    # ---- Privacy by design ----
    C["p1_frontier"] = dict(
        page="privacy", title="What does each field buy us, and what does it cost? (the minimization frontier)", datasets=["frontier"], evaluation=True,
        question="What does each field buy us, and what does it cost? (the privacy lead, then clubs)",
        spec={"data": _src("frontier"), "width": "container", "height": 330, "layer": [
            {"mark": {"type": "line", "color": "#8A96A3", "strokeDash": [4, 3]}, "encoding": {"x": {"field": "pct_unique", "type": "quantitative", "title": "Participant-years that are unique (%), lower is safer", "scale": {"zero": False}},
                "y": {"field": "f1", "type": "quantitative", "scale": {"domain": [0.97, 1]}, "title": "Identity F1 (final matcher, before review)"}, "order": {"field": "variant_id"}}},
            {"mark": {"type": "point", "filled": True, "size": 120}, "encoding": {"x": {"field": "pct_unique", "type": "quantitative"}, "y": {"field": "f1", "type": "quantitative"},
                "color": {"field": "variant_id", "type": "nominal", "title": "Variant"}, "tooltip": [{"field": "variant_label"}, {"field": "precision"}, {"field": "recall"}, {"field": "sibling_or_twin_false_merges"},
                                                                                                   {"field": "pct_rows_below_k_min"}, {"field": "fit_for_activate"}]}},
            {"mark": {"type": "point", "filled": False, "size": 520, "strokeWidth": 3}, "encoding": {"x": {"field": "pct_unique", "type": "quantitative"}, "y": {"field": "f1", "type": "quantitative"},
                "stroke": {"field": "in_standard", "type": "nominal", "scale": {"domain": [True, False], "range": ["#000000", "rgba(0,0,0,0)"]}, "legend": None}}},
            {"mark": {"type": "text", "dy": -14, "fontSize": 11}, "encoding": {"x": {"field": "pct_unique", "type": "quantitative"}, "y": {"field": "f1", "type": "quantitative"}, "text": {"field": "variant_id", "type": "nominal"}}}]},
        shows="One point per field-granularity variant, from the full date of birth and postal code (V0) to a birth year, ZIP3 and a hashed email (V4). Left is safer (fewer participant-years are unique); higher is a more accurate identity match. Dropping the day of birth and ZIP5 costs the matcher almost nothing here.",
        doesnt="The whole story: the ringed point (V2) is the variant the data standard cites, chosen by the program owner on 2026-10-14 from this frontier (ADR-018), not an optimum. Share below k_min is above 97% for every variant, so it cannot separate them and the horizontal axis uses the share of unique participant-years instead. One synthetic dataset, so read the pattern, not the decimals.",
        note=lambda d: "The ringed point is the data standard's choice (V2: birth year, ZIP3, email and an optional phone for matching). A hashed email (V4) matches as well as a clear one and gives up the activation purpose entirely.",
        lens=dict(club="The cost to a club is in the last column of the table: a hashed contact cannot reach a family.", privacy="Only the x-axis is a privacy measure; the y-axis is what identity resolution keeps."))
    C["p2_provenance"] = dict(
        page="privacy", title="Do we know what families agreed to? (consent provenance)", datasets=["consent_prov"],
        question="Do we know what families agreed to? (the privacy lead)",
        spec={"data": _src("consent_prov"), "width": "container", "height": 300, "mark": {"type": "bar"},
              "encoding": {"y": {"field": "form", "type": "nominal", "title": None}, "x": {"field": "x0", "type": "quantitative", "title": "Consent events, latest season"}, "x2": {"field": "x1"},
                           "color": {"field": "provenance_grade", "type": "nominal", "title": "Provenance",
                                     "scale": {"domain": ["KNOWN_FULL", "KNOWN_PARTIAL", "UNKNOWN"], "range": ["#2F6B4F", "#B8A06A", "#8A96A3"]}}, "tooltip": [{"field": "form"}, {"field": "provenance_grade"}, {"field": "consent_events"}]}},
        shows="For each source and consent wording, how many consent events are fully evidenced (wording, time and purpose known), partly evidenced, or unknown. The bars are in events.",
        doesnt="Whether a family would agree today, or that a fully evidenced consent was valid: provenance is about what is on record. A cell with fewer than k_min events is hidden and shows as <k in the table.",
        lens=dict(club="Unknown provenance means the family cannot be contacted for marketing, whatever they ticked.", privacy="This is the chart behind the claim that a consent email is not a marketing opt-in."))
    C["p3_matrix"] = dict(
        page="privacy", title="Which purposes can we lawfully pursue, per form? (purpose coverage)", datasets=["purpose_matrix"],
        question="Which purposes can we pursue, per form? (the privacy lead)",
        spec={"data": _src("purpose_matrix"), "width": "container", "height": 160, "layer": [
            {"mark": {"type": "rect", "stroke": "#ffffff"}, "encoding": {"x": {"field": "purpose_label", "type": "nominal", "title": None}, "y": {"field": "consent_text_version", "type": "nominal", "title": None},
                "color": {"field": "coverage", "type": "nominal", "scale": {"domain": ["Named on the form", "Not named"], "range": ["#92c5de", "#f4a582"]}, "title": "Wording"}}},
            {"mark": {"type": "text", "fontSize": 14}, "encoding": {"x": {"field": "purpose_label", "type": "nominal"}, "y": {"field": "consent_text_version", "type": "nominal"}, "text": {"field": "mark", "type": "nominal"}}}]},
        shows="For each consent wording, whether the form names each purpose (yes) or not (no). Only a form that names club marketing can carry a club-marketing opt-in.",
        doesnt="Legal advice or a finding about any form: whether a wording is sufficient is a question for counsel. This chart reads the wording the generator gave each form, and a purpose that needs its own consent is never covered by a terms acceptance.",
        lens=dict(club="Only the last wording lets a club market to the family.", privacy="Purpose limitation: a yes here is necessary, not sufficient."))
    C["p5_retention"] = dict(
        page="privacy", title="Can we delete and still measure retention? (analytics after the age-out deletion)", datasets=["retention_del"],
        question="Can we delete and still measure retention? (the privacy lead)",
        spec={"data": _src("retention_del"), "width": "container", "height": 300, "mark": {"type": "bar"},
              "encoding": {"y": {"field": "metric_label", "type": "nominal", "title": None}, "x": {"field": "change", "type": "quantitative", "axis": {"format": "%"}, "title": "Change in the figure after deletion"},
                           "yOffset": {"field": "scenario", "type": "nominal"}, "color": {"field": "scenario", "type": "nominal", "title": None, "scale": {"range": ["#2F6B4F", "#D9622B"]}}}},
        shows="How much each retention figure moves when children who aged out are anonymized: not at all if the marts are rebuilt from the pseudonymous facts, by about a sixth if identity resolution is re-run on the anonymized inputs.",
        doesnt="The loss of re-linking a returning adult to their youth history: this synthetic data has no child who plays on as an adult inside the window, so that case is zero here and cannot be shown. The retention periods are assumptions.",
        lens=dict(club="Retention rates survive if the pipeline keeps the pseudonymous key.", privacy="The design constraint: freeze the participant key before the identifiers go, and never re-run identity over deleted records (ADR-017)."))
    return C


def render_fix_card(rows) -> str:
    from html import escape as e
    if not rows:
        return "<p class='note'>No fix list for the latest season.</p>"
    items = "".join(f"<li><b>{r['rank']}. {e(r['rule_id'])}</b><br>{e(r['fix_guidance'])}<br><span class='note'>{r['records_affected']:,} records affected · about {r['impact_estimate']:.0f} {e(str(r['impact_unit']).lower())} · owner: {e(r['owner_role'])}</span></li>"
                    for r in rows)
    return f"<div class='card'><p class='note'><b>{e(rows[0]['organization'])}</b> · what to fix first</p><ol>{items}</ol></div>"


PAGE_HEAD = {
    "quality": ("Data quality", "Which data can we trust, for which purpose, and what should be fixed first?"),
    "sure": ("How sure are we?", "Why there is a range and not one number, and what narrows it."),
    "markets": ("Club markets", "How is my market doing, and why can't we reach more families?"),
    "privacy": ("Privacy by design", "What do we collect, why, and what does that cost?"),
}
PAGES = [("quality", "Data quality"), ("sure", "How sure"), ("markets", "Club markets"), ("privacy", "Privacy by design")]
DEMO_PATH = {
    "quality": "The purpose heatmap (the same data earns different grades), then the Pareto (which few fixes matter).",
    "sure": "The three separate bars (why there is no single number), then the fix-list payoff.",
    "markets": "The tile map (find a market), then the funnel (why families are not reached), then the two lenses.",
    "privacy": "The minimization frontier, then consent provenance.",
}
