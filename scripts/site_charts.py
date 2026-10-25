"""The results site's chart specifications (Vega-Lite, mapping fields to marks only) and the server-side drive chart.

Split out of scripts/build_site.py without changing a line. A spec may not calculate, aggregate, bin, fold or window: see `site_rules.check_spec`.
"""
from __future__ import annotations

from scripts import site_phase5 as P5, site_product
from scripts.site_render import esc


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
EST_ORDER = ["Naive comparison (existing fans)", "Matched before/after"]
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
              "color": {"field": "view", "type": "nominal", "title": None}}})
    C["girls"] = dict(
        page="participation", title="Girls' share of youth participation", datasets=["girls_share"],
        spec={"data": _src("girls_share"), "width": "container", "height": 260, "mark": {"type": "line", "point": True},
              "encoding": {"x": {"field": "participation_year", "type": "ordinal", "title": "Participation year"},
              "y": {"field": "girls_share_of_youth", "type": "quantitative", "axis": {"format": "%", "title": "Girls' share of youth"}, "scale": {"zero": False}}}})
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
              "y": {"field": "sibling_or_twin_false_merges", "type": "quantitative", "title": "Sibling / twin false merges"}}})
    C["retention_km"] = dict(
        page="participation", title="Retention by entry age band (Kaplan-Meier, with 95% intervals)", datasets=["retention_km_age"],
        spec={"data": _src("retention_km_age"), "width": "container", "height": 320, "layer": [
            {"mark": {"type": "area", "opacity": 0.12}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative", "title": "Years since entry", "axis": {"tickMinStep": 1}},
             "y": {"field": "km_survival_ci_low", "type": "quantitative", "scale": {"domain": [0, 1]}, "axis": {"format": "%", "title": "Still registered"}},
             "y2": {"field": "km_survival_ci_high"}, "color": {"field": "segment_value", "type": "nominal", "title": "Entry age", "sort": AGE_ORDER, "scale": {"domain": AGE_ORDER}}}},
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative"},
             "y": {"field": "km_survival", "type": "quantitative"}, "color": {"field": "segment_value", "type": "nominal", "sort": AGE_ORDER, "scale": {"domain": AGE_ORDER}}}}]})
    C["retention_sex"] = dict(
        page="participation", title="Retention by sex", datasets=["retention_km_sex"],
        spec={"data": _src("retention_km_sex"), "width": "container", "height": 260, "layer": [
            {"mark": {"type": "area", "opacity": 0.15}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative", "title": "Years since entry", "axis": {"tickMinStep": 1}},
             "y": {"field": "km_survival_ci_low", "type": "quantitative", "scale": {"domain": [0, 1]}, "axis": {"format": "%", "title": "Still registered"}},
             "y2": {"field": "km_survival_ci_high"}, "color": {"field": "segment_value", "type": "nominal", "title": "Sex"}}},
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "years_since_entry", "type": "quantitative"},
             "y": {"field": "km_survival", "type": "quantitative"}, "color": {"field": "segment_value", "type": "nominal"}}}]})
    C["cohorts"] = dict(
        page="participation", title="Cohort triangle: share of each entry cohort still registered", datasets=["retention_cohorts"],
        spec={"data": _src("retention_cohorts"), "width": "container", "height": 220, "mark": "rect",
              "encoding": {"x": {"field": "years_since_entry", "type": "ordinal", "title": "Years since entry"},
              "y": {"field": "entry_year", "type": "ordinal", "title": "Entry cohort"},
              "color": {"field": "cohort_retention_pct", "type": "quantitative", "scale": {"domain": [0, 1], "scheme": "blues"}, "legend": {"format": "%", "title": "Still registered"}}}})
    C["naive_vs_censored"] = dict(
        page="participation", title="Entrants aged 14 to 17: naive vs censored vs the truth", datasets=["retention_vs_truth"], evaluation=True,
        spec={"data": _src("retention_vs_truth"), "width": "container", "height": 300, "mark": {"type": "line", "point": True},
              "encoding": {"x": {"field": "years_since_entry", "type": "quantitative", "title": "Years since entry", "axis": {"tickMinStep": 1}},
              "y": {"field": "survival", "type": "quantitative", "scale": {"domain": [0, 1]}, "axis": {"format": "%", "title": "Still registered"}},
              "color": {"field": "curve", "type": "nominal", "title": None, "legend": {"orient": "bottom", "columns": 1}},
              "strokeDash": {"field": "curve", "type": "nominal", "legend": None,
                             "scale": {"domain": ["true (generator parameters)", "Kaplan-Meier (age-outs censored)", "naive (age-out counted as churn)"], "range": [[1, 0], [1, 0], [6, 4]]}}}})
    C["fan_estimates"] = dict(
        page="value", title="Does registering a child raise a household's fan engagement? Naive vs matched vs truth", datasets=["fan_vs_truth"], evaluation=True,
        spec={"data": _src("fan_vs_truth"), "width": "container", "height": 300, "transform": [{"filter": "datum.estimator !== 'Naive, all linked accounts (analyst detail)'"}], "layer": [
            {"mark": {"type": "bar", "opacity": 0.8}, "encoding": {"x": {"field": "estimator", "type": "nominal", "title": None, "sort": EST_ORDER},
             "y": {"field": "estimate_pct", "type": "quantitative", "axis": {"format": "%", "title": "Change in events per household-month"}}}},
            {"mark": {"type": "rule", "strokeWidth": 2}, "encoding": {"x": {"field": "estimator", "type": "nominal", "sort": EST_ORDER},
             "y": {"field": "ci_low_pct", "type": "quantitative"}, "y2": {"field": "ci_high_pct"}}},
            {"mark": {"type": "tick", "color": "#D9622B", "thickness": 3, "size": 70}, "encoding": {"x": {"field": "estimator", "type": "nominal", "sort": EST_ORDER},
             "y": {"field": "true_effect_pct", "type": "quantitative"}}}]})
    C["event_study"] = dict(
        page="value", title="Event study: mean fan events per month around the first registration", datasets=["fan_event_study"],
        spec={"data": _src("fan_event_study"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "line", "point": True}, "encoding": {"x": {"field": "months_since_event", "type": "quantitative", "title": "Months since first registration"},
             "y": {"field": "mean_events", "type": "quantitative", "title": "Events per household-month"}, "color": {"field": "group_name", "type": "nominal", "title": None}}},
            {"mark": {"type": "rule", "strokeDash": [4, 4]}, "encoding": {"x": {"datum": 0, "type": "quantitative"}}}]})
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
            {"mark": {"type": "tick", "color": "#D9622B", "thickness": 3, "size": 90}, "encoding": {"x": {"field": "method", "type": "nominal", "sort": ORDER}, "y": {"field": "true_incremental_accounts", "type": "quantitative"}}}]})
    C["drive"] = dict(
        page="acquisition", title="The drive chart: from registered household to active fan", datasets=["drive_stages"], spec=None, render=render_drive)
    C["funnel_status"] = dict(
        page="acquisition", title="What fan status do registered households have?", datasets=["fan_status_mix"],
        spec={"data": _src("fan_status_mix"), "width": "container", "height": 280, "mark": "bar",
              "encoding": {"x": {"field": "households", "type": "quantitative", "title": "Registered households, latest cohort"}, "y": {"field": "fan_status", "type": "nominal", "sort": "-x", "title": None}}})
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
              "color": {"field": "segment", "type": "nominal", "title": "RFM segment"}}})
    C["fan_survival"] = dict(
        page="value", title="How long do fan accounts stay active? (Kaplan-Meier, 95% intervals)", datasets=["fan_survival"],
        spec={"data": _src("fan_survival"), "width": "container", "height": 300, "layer": [
            {"mark": {"type": "area", "opacity": 0.12}, "encoding": {"x": {"field": "months_since_origin", "type": "quantitative", "title": "Months since account origin"},
             "y": {"field": "fan_survival_ci_low", "type": "quantitative", "scale": {"domain": [0, 1]}, "axis": {"format": "%", "title": "Not lapsed"}}, "y2": {"field": "fan_survival_ci_high"},
             "color": {"field": "fan_group", "type": "nominal", "title": "Fan group"}}},
            {"mark": {"type": "line"}, "encoding": {"x": {"field": "months_since_origin", "type": "quantitative"}, "y": {"field": "fan_survival", "type": "quantitative"}, "color": {"field": "fan_group", "type": "nominal"}}}]})
    C["fan_ltv"] = dict(
        page="value", title="Modelled lifetime value per fan account (synthetic currency)", datasets=["fan_ltv"],
        spec={"data": _src("fan_ltv"), "width": "container", "height": 260, "layer": [
            {"mark": {"type": "bar", "opacity": 0.8}, "encoding": {"x": {"field": "fan_group", "type": "nominal", "title": None, "axis": {"labelAngle": 0, "labelLimit": 200}}, "y": {"field": "fan_ltv", "type": "quantitative", "title": "Value over the horizon, synthetic currency"}}},
            {"mark": {"type": "rule", "strokeWidth": 2}, "encoding": {"x": {"field": "fan_group", "type": "nominal"}, "y": {"field": "fan_ltv_low", "type": "quantitative"}, "y2": {"field": "fan_ltv_high"}}}]})
    C["uplift_events"] = dict(
        page="value", title="Existing fans: events per household-month after registering a child", datasets=["uplift_events"],
        spec={"data": _src("uplift_events"), "width": "container", "height": 240, "layer": [
            {"mark": {"type": "bar", "opacity": 0.8}, "encoding": {"x": {"field": "uplift_status_group", "type": "nominal", "title": "Status before registering", "axis": {"labelAngle": 0}}, "y": {"field": "uplift_per_month", "type": "quantitative", "title": "Extra events per household-month"}}},
            {"mark": {"type": "rule", "strokeWidth": 2}, "encoding": {"x": {"field": "uplift_status_group", "type": "nominal"}, "y": {"field": "uplift_ci_low_per_month", "type": "quantitative"}, "y2": {"field": "uplift_ci_high_per_month"}}}]})
    C["uplift_spend"] = dict(
        page="value", title="Existing fans: net spend per household-month after registering a child (synthetic currency)", datasets=["uplift_spend"],
        spec={"data": _src("uplift_spend"), "width": "container", "height": 240, "layer": [
            {"mark": {"type": "bar", "opacity": 0.8}, "encoding": {"x": {"field": "uplift_status_group", "type": "nominal", "title": "Status before registering", "axis": {"labelAngle": 0}}, "y": {"field": "uplift_per_month", "type": "quantitative", "title": "Extra net spend per household-month"}}},
            {"mark": {"type": "rule", "strokeWidth": 2}, "encoding": {"x": {"field": "uplift_status_group", "type": "nominal"}, "y": {"field": "uplift_ci_low_per_month", "type": "quantitative"}, "y2": {"field": "uplift_ci_high_per_month"}}}]})
    # ---- audience and consent ----
    C["audience"] = dict(
        page="audience", title="The addressable audience and the consent gap over time", datasets=["audience_series"],
        spec={"data": _src("audience_series"), "width": "container", "height": 320, "mark": {"type": "line"},
              "encoding": {"x": {"field": "month", "type": "temporal", "title": None}, "y": {"field": "households", "type": "quantitative", "title": "Households"},
              "color": {"field": "measure", "type": "nominal", "title": None, "legend": {"orient": "bottom", "columns": 2}}}})
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
              "color": {"field": "quadrant", "type": "nominal", "title": "Quadrant"}, "tooltip": [{"field": "market_name"}, {"field": "quadrant"}]}})
    # descriptions from the plain-language walkthrough: plain terms (shows), the design choice (decision) and the limitations (doesnt)
    DESCRIPTIONS = {
        "acq_estimates": dict(
            shows="The careful estimate of how many fan accounts exist because of flag football sits close to the red tick (the built-in truth). Counting every new sign-up instead overshoots badly once it is scaled up for families the data cannot see. In plain terms: the careful method is right for the right reason, while the linked-only count looks close but is close by accident, and with a different link rate it could be far off.",
            decision="The estimate uses the staggered rollout (markets launching in different years) as a natural experiment, rather than surveying families.",
            doesnt="A precise number. The estimate is only as good as the comparison between launched and not-yet-launched markets, and the range is wide because few markets stand behind each year. The linked-only count looks close to the truth only because two errors partly cancel: it credits every sign-up to the programme but ignores families it cannot see.",
        ),
        "drive": dict(
            shows="Of all registered households, only about a third can be matched to a fan account; of those, most can be contacted and most are active. In plain terms: among the families we can see, most are engaged, but we can see only about a third of them. The rest have unknown fan status.",
            decision="Unlinked families sit in their own striped lane, labelled \"unknown\", not \"non-fan\". Treating them as non-fans would make the programme look worse than it is.",
            doesnt="A strict funnel. Contactable and active are both shares of linked households and they overlap: some active families never opted in. Paying and retained fans are not in the executive view yet.",
        ),
        "funnel_status": dict(
            shows="Registered households of the latest cohort by fan status. In plain terms: most families are invisible to the fan data, and among the visible ones existing fans dominate, so much of what the programme \"reaches\" was already a fan.",
            doesnt="How many unlinked households really are fans: some have an account the identity matcher could not find. Without identity resolution, a child in several leagues would also inflate this household count. This chart covers the latest cohort, while the drive chart covers the latest month, so do not compare the two totals directly.",
        ),
        "fan_estimates": dict(
            shows="Families who register a child engage more afterwards. In plain terms: the careful (matched) estimate slightly overshoots the truth, and the simple comparison slightly undershoots it.",
            decision="Each registering household is matched to a similar non-registering household, based on its engagement before registration, and both are compared before and after.",
            doesnt="A result for all participants: it covers households linked to a fan account (mostly North American). Matching on past behaviour did not fully balance underlying fandom, so the matched figure leans high and its interval is a little too narrow (ADR-010). Read it as an upper-leaning estimate.",
        ),
        "event_study": dict(
            shows="Before registration, participants and their matched comparisons move together; afterwards participants stay higher. In plain terms: the two groups were alike before and diverge after. The bumps repeat each year because engagement follows the NFL season.",
            doesnt="A tight estimate: a tiny gap remains before registration (residual selection), which the matched estimate subtracts. The vertical dashed line is month 0.",
        ),
        "rfm": dict(
            shows="Existing fans are mostly Champions and Loyal; net-new fans have more Promising and Hibernating accounts. In plain terms: established fans are the core spenders, and new fans are earlier in their journey. The two net-new groups look almost identical: fans who arrived through the flag prompt have about the same mix as fans who arrived some other way (about 19% Champions, 12 to 13% Promising, 17 to 19% Hibernating). That is the business point of this chart: fans acquired through flag football are not lower-quality fans, and they are as engaged as fans acquired any other way.",
            doesnt="Absolute value: segments are based on quintiles, which are relative, so every group has some Champions by construction. Compare the mix between groups, not the labels.",
        ),
        "fan_survival": dict(
            shows="Existing fans stay active longest; net-new fans from other routes come next; fans prompted by flag football lapse soonest, with wide uncertainty bands.",
            decision="A survival method (Kaplan-Meier) is used: accounts still active when the data ends count as \"not yet lapsed\", not as lapsed.",
            doesnt="Why accounts lapse. Groups were not randomly assigned, so differences mix who joins with what the programme does.",
        ),
        "fan_ltv": dict(
            shows="In plain terms: a fan created by flag football is worth almost as much as one acquired another way.",
            doesnt="Revenue. This is net spend per month times expected active months, an illustration in synthetic currency. The narrow ranges reflect sampling only, not uncertainty in the modelling assumptions, so they understate real uncertainty.",
        ),
        "uplift_events": dict(
            shows="In plain terms: registering a child lifts engagement even among families who were already fans, and lapsed fans come back with a similar lift.",
            decision="For lapsed fans the change is shown in absolute terms, not as a percentage: their starting point is near zero, so a percentage would look enormous and mislead.",
            doesnt="A result for unlinked households. The intervals are wide and overlap, so the difference between groups is not reliable.",
        ),
        "uplift_spend": dict(
            shows="In plain terms: registering a child lifts spending even among families who were already fans. Lapsed fans show the largest spending bump, which suggests flag football can win back former fans.",
            doesnt="Revenue: the currency is synthetic and refunds are netted out of spend. It covers linked households only, and the intervals are wide and overlap, so the difference between groups is not reliable.",
        ),
        "audience": dict(
            shows="Registered households rise in steps, each step a new group of markets launching, while linked, contactable and active households grow much more slowly; the consent gap creeps up. In plain terms: registrations have grown more than tenfold, but the reachable audience has not kept pace, because most new families cannot be linked.",
            doesnt="A marketing list: these are counts, and no household is identified here or anywhere an audience can see. A household with no consent record is not contactable, and no record is not the same as a \"no\".",
        ),
        "market_quadrants": dict(
            shows="Each synthetic market with enough participant households, by participation and fan accounts per 1,000 households, split at the medians. Retention and engagement play: strong on both, keep fans engaged. Long-term build: weak on both, slow investment. Programme growth opportunity: strong fan base, low participation, grow the programme. Acquisition white space: high participation, weaker fan base, convert players' families into fans.",
            decision="Markets with too few participant households are rolled up and not drawn, to protect small numbers.",
            doesnt="Real places: the markets are invented. A quadrant says where to look, not what to do.",
        ),
        "country": dict(
            shows="Participants by country in the latest year, as two views of the same children side by side.",
            decision="\"Attributed\" counts each child once, in the country of their latest registration, so it adds up to a total. \"Present\" counts a child in every country they played in.",
            doesnt="A global total: the \"present\" view must never be summed, since children who played in two countries would be counted twice. Small country counts are hidden rather than shown.",
        ),
        "girls": dict(
            shows="In plain terms: flag football is moving steadily towards gender parity.",
            doesnt="Why the share is moving. It uses sex as recorded at registration, not gender identity. Children with no recorded sex stay in the denominator, so the share is slightly understated. The axis is zoomed in, which makes the rise look steeper than it is.",
        ),
        "retention_km": dict(
            shows="In plain terms: children who start young are far more likely to keep playing.",
            decision="A player who turns 18, or whose records simply end, is treated as \"no longer observed\" (censored), not as having quit. Steps with fewer than 10 players at risk are not shown.",
            doesnt="Why players leave, or what the curves would be for adults continuing after 17 (this synthetic world has no adult continuation).",
        ),
        "retention_sex": dict(
            shows="In plain terms: girls stay as long as boys. The tiny gap is within the noise.",
            doesnt="A causal difference. Segments overlap (age and division describe largely the same players) and nobody was assigned to them.",
        ),
        "cohorts": dict(
            shows="For each entry year, the share of that cohort registered again one, two and three years later (only years that have happened). Retention drops each year, to roughly a third of a cohort by year three.",
            doesnt="Retention corrected for ageing out: older youth disappear because they turn 18, not because they chose to leave. The corrected version is in the table below.",
        ),
        "naive_vs_censored": dict(
            shows="In plain terms: if you count a 17-year-old who turns 18 as a dropout, teenage retention looks 22 to 24 points worse than it really is. Treating the birthday as censoring lands near the true churn.",
            decision="This chart is the justification for the censoring rule. For younger entrants, who do not turn 18 within the five-year window, the naive and corrected curves are the same, so the rule only matters for teens.",
            doesnt="Real churn: the truth here is the generator's own parameters, so this shows the rule works on known data, not what real players do.",
        ),
        "siblings": dict(
            shows="In plain terms: merging siblings is not just a counting error; it mixes two children's personal data, which is a privacy incident. The chart counts how many times two different children of one household were merged at each threshold.",
            decision="The final matcher has a household guard against sibling merges, and a data steward reviews the borderline \"probable\" pairs.",
            doesnt="That a merge is harmless, or real-world performance: the sibling and twin merges that remain are the incidents that matter.",
        ),
    }
    for cid, d in DESCRIPTIONS.items():
        C[cid].update(d)
    # notes that sit under a chart; each gets the exported datasets and returns plain text built from them
    C["participation_trend"]["note"] = note_participation_trend
    C["funnel_rates"]["note"] = lambda d: ("Dormant lapsed households have no bars for Active and Monetized: they are zero by definition (a household that is still dormant is not active, so it cannot be monetized), "
                                           "not missing data.")
    C["acq_event_study"]["note"] = lambda d: ("Only one pre-launch year (two years before launch) is observed, because every market in this synthetic world launches in year 1 or later and year -1 is the reference year. "
                                              "A flat pre-period therefore rests on a single point.")
    C["market_quadrants"]["note"] = note_market_quadrants
    C.update(P5.charts())
    C.update(site_product.charts())
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
