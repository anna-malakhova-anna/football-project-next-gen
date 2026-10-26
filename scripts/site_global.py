"""Phase 7 (spec section 11): the Global outlook tab of the results site, the 22 markets of the NFL Global Markets Program, flag football only.

Imported by scripts/build_site.py (the page and its cards), scripts/site_data.py (the datasets and what they may read) and scripts/site_render.py (labels).
The same rules as everywhere on the site: every number comes from a registered dataset (DP6's exec ports, whitelisted evaluation summaries, governance
metadata); a chart spec only maps fields to marks; every label, order and position is worked out in SQL. The planning scenario never appears on the
same chart as a measured value, and the card that grades it against the answer key carries the synthetic-evaluation tag. All data is SYNTHETIC.
"""
from __future__ import annotations

from html import escape as e

SHARE_MARKETS = ["share_exec.share_exec__gmp_markets_eu_uk", "share_exec.share_exec__gmp_markets_canada", "share_exec.share_exec__gmp_markets_other"]
SHARE_TREND = ["share_exec.share_exec__gmp_quality_trend_eu_uk", "share_exec.share_exec__gmp_quality_trend_canada", "share_exec.share_exec__gmp_quality_trend_other"]
EVAL = {"evaluation.eval_gmp_scenario", "evaluation.eval_gmp_scenario_summary"}
GOVERNANCE = {"reference.gmp_markets", "reference.dq_grade_bands", "reference.p7_params"}
STATUS_LABEL = ("case status when 'MEASURED' then 'Measured' when 'PARTIAL' then 'Partial' when 'PROXY_ONLY' then 'Clubs report activity' else 'Nothing arrives' end")
STATUS_ORDER = "case status when 'MEASURED' then 1 when 'PARTIAL' then 2 when 'PROXY_ONLY' then 3 else 4 end"
DIRECTION_LABEL = ("case participation_direction when 'GROWING' then 'Growing' when 'SHRINKING' then 'Shrinking' when 'FLAT' then 'No change we can tell' "
                   "when 'NOT_DETECTABLE' then 'Too few clubs to tell' else 'Not measured' end")


def _union(tables: list[str]) -> str:
    return " union all ".join(f"select * from {t}" for t in tables)


def _D(name, sql, relations, kind, title):
    return {"name": name, "sql": sql.strip(), "relations": set(relations), "kind": kind, "title": title}


DATASETS = [
    _D("gmp_markets", f"""
        with m as ({_union(SHARE_MARKETS)})
        select country_code, country_name, region, status, {STATUS_LABEL} as status_label, {STATUS_ORDER} as status_order,
               coalesce(counting_grade, '') as grade, {DIRECTION_LABEL} as direction_label, clubs_with_rights, regime_name
        from m order by status_order, country_name""", SHARE_MARKETS, "share_exec", "The 22 program markets: what we can read in each (latest season)"),
    _D("gmp_growth", f"""
        with m as ({_union(SHARE_MARKETS)})
        select country_name, {STATUS_LABEL} as status_label, growth_pct as growth_percent, minimum_detectable_change_pct as change_needed,
               -minimum_detectable_change_pct as change_needed_down, {DIRECTION_LABEL} as direction_label,
               case when growth_pct is null then 'hidden' else cast(growth_pct as varchar) || '%' end as growth_text
        from m where status in ('MEASURED', 'PARTIAL') order by growth_pct desc nulls last, country_name""", SHARE_MARKETS, "share_exec",
       "Like-for-like growth since the previous season, against the change needed to tell growth from noise"),
    _D("gmp_eval", """
        select g.country_name, e.scenario_low, e.scenario_high, e.true_participants,
               case e.truth_vs_range when 'INSIDE' then 'Inside the guess' when 'ABOVE' then 'Above the guess' else 'Below the guess' end as truth_label,
               case when e.set_against_comparables then 'Moved against its neighbours' else 'Moved with its neighbours' end as built_as
        from evaluation.eval_gmp_scenario e join reference.gmp_markets g using (country_code)
        order by e.true_participants desc""", ["evaluation.eval_gmp_scenario", "reference.gmp_markets"], "evaluation",
       "SYNTHETIC EVALUATION: the planning scenario's range against the answer key's true players, markets with no data"),
    _D("gmp_eval_summary", """
        select case market_group when 'ALL' then 'All markets with no data' when 'WITH_COMPARABLES' then 'Moved with their neighbours' else 'Moved against their neighbours' end as market_group_label,
               markets, truth_in_range, truth_above_range, truth_below_range, direction_wrong, proxy_direction_known, proxy_direction_right
        from evaluation.eval_gmp_scenario_summary
        order by case market_group when 'ALL' then 0 when 'WITH_COMPARABLES' then 1 else 2 end""", ["evaluation.eval_gmp_scenario_summary"], "evaluation",
       "SYNTHETIC EVALUATION: how often the planning scenario was right"),
    _D("gmp_trend", f"""
        with t as ({_union(SHARE_TREND)}),
             bar as (select min_score from reference.dq_grade_bands where grade = (select value from reference.p7_params where param = 'measured_min_grade'))
        select t.country_name, t.season_year, t.counting_score, t.counting_grade, t.clubs_filed, t.clubs_known,
               cast(t.clubs_filed as varchar) || ' of ' || cast(t.clubs_known as varchar) as clubs_text, bar.min_score as measured_bar
        from t cross join bar order by t.country_name, t.season_year""", SHARE_TREND + ["reference.dq_grade_bands", "reference.p7_params"], "share_exec",
       "Counting score per market and season, with the bar a market must clear to read Measured"),
    _D("gmp_board", f"""
        select country_name, lane, case lane when 'NOW' then 'Now' when 'NEXT' then 'Next' when 'LATER' then 'Later' else 'Keep' end as lane_label,
               case lane when 'NOW' then 1 when 'NEXT' then 2 when 'LATER' then 3 else 4 end as lane_order, action,
               case gate_status when 'MET' then 'Met' when 'NOT_YET' then 'Not yet' else 'Waiting for data' end as gate_text,
               case gate_kind when 'COUNTING_GRADE_AT_LEAST' then 'Counting grade ' || target || ' or better' when 'MIN_RETURN_SEASONS' then 'A first season of counts'
                    else 'Clubs file an activity return' end as gate_label,
               bar_fill_pct as progress_percent, {STATUS_LABEL} as status_label, priority_rank,
               case score_status when 'DRAFT' then 'Draft score' when 'AGREED_RUBRIC' then 'Agreed rule' else 'Set by Anna' end as score_text
        from share_exec.share_exec__gmp_board order by lane_order, priority_rank""", ["share_exec.share_exec__gmp_board"], "share_exec",
       "The market board: what to do next in each market, with progress (lanes and scores are drafts)"),
    _D("gmp_walkthrough", """
        select country_name, stage_order, stage, case state when 'DONE' then 'Done' when 'EXPERIMENT' then 'Tried on a copy' else 'Not started' end as state_label,
               artifact, what_happened from share_exec.share_exec__gmp_walkthrough order by country_name, stage_order""", ["share_exec.share_exec__gmp_walkthrough"], "share_exec",
       "Onboarding walkthroughs: Canada (has data) and Italy (no data yet), stage by stage"),
    _D("chart_insights_exec_global", "select chart_id, lens, field, value_display, value_raw, suppressed from share_exec.share_exec__gmp_chart_insights order by 1, 3",
       ["share_exec.share_exec__gmp_chart_insights"], "share_exec", "Numbers used in the Global outlook headlines"),
]

COLUMN_LABELS = {
    "status_label": "What we can read", "status_order": "Order", "direction_label": "Direction", "clubs_with_rights": "Clubs with rights", "regime_name": "Privacy law (assumed)",
    "growth_percent": "Growth (%)", "change_needed": "Change needed (%)", "change_needed_down": "Change needed, down (%)", "growth_text": "Growth",
    "true_participants": "True players (answer key)", "scenario_low": "Guess, low", "scenario_high": "Guess, high", "truth_label": "Truth", "built_as": "Answer key built as",
    "market_group_label": "Markets", "truth_in_range": "Truth inside the guess", "truth_above_range": "Truth above", "truth_below_range": "Truth below",
    "direction_wrong": "Direction wrong", "proxy_direction_known": "Club activity known", "proxy_direction_right": "Club activity right",
    "counting_score": "Counting score", "counting_grade": "Counting grade", "clubs_filed": "Clubs that sent a file", "clubs_known": "Clubs known", "clubs_text": "Clubs that sent a file",
    "measured_bar": "Bar for Measured", "lane_label": "Lane", "lane_order": "Order", "action": "What to do", "gate_text": "Progress", "gate_label": "Milestone",
    "progress_percent": "Progress (%)", "priority_rank": "Priority rank", "score_text": "Score", "stage_order": "Step", "stage": "Stage", "state_label": "State",
    "artifact": "Evidence", "what_happened": "What happened", "country_name": "Market", "region": "Region", "grade": "Grade", "lane": "Lane",
}


# ------------------------------------------------------------------ charts
def _src(name):
    return {"url": f"data/{name}.json", "format": {"type": "json", "property": "rows"}}


def render_markets(rows, compact=False) -> str:
    """The 22 markets as tiles grouped by what we can read: a market with data shows its counting grade colour; clubs-only markets an outline; dark markets a dashed outline."""
    groups: dict = {}
    for r in sorted(rows, key=lambda r: (r["status_order"], r["country_name"])):
        groups.setdefault(r["status_label"], []).append(r)
    out = []
    for label, tiles in groups.items():
        cells = []
        for t in tiles:
            cls = f"g-{t['grade']}" if t["grade"] else ("g-hidden" if t["status"] == "PROXY_ONLY" else "g-none")
            detail = f"<span class='mdetail'>{e(t['direction_label'])}</span>" if t["grade"] else ""
            cells.append(f"<div class='mtile {cls}' title='{e(t['country_name'])}: {e(label)}'><span class='mletter'>{e(t['grade']) or '&nbsp;'}</span>"
                         f"<span class='mname'>{e(t['country_name'])}</span>{detail}</div>")
        out.append(f"<div class='vstate'><h4>{e(label)} ({len(tiles)})</h4><div class='vstate-row'>{''.join(cells)}</div></div>")
    return f"<div class='vtiles-single'><div class='vtiles{' vtiles-compact' if compact else ''}'>{''.join(out)}</div></div>"


def render_board(rows, compact=False) -> str:
    """The market board: one lane per heading, one tile per market with its next action and milestone progress (drafts)."""
    lanes: dict = {}
    for r in sorted(rows, key=lambda r: (r["lane_order"], r["priority_rank"])):
        lanes.setdefault(r["lane_label"], []).append(r)
    out = []
    for label, tiles in lanes.items():
        cells = []
        for t in tiles:
            detail = "" if compact else f"<span class='mdetail'>{e(t['action'])}</span><span class='mdetail'>{e(t['gate_label'])}: {e(t['gate_text'])}</span>"
            cells.append(f"<div class='mtile g-hidden' title='{e(t['country_name'])}: {e(t['action'])}'><span class='mname'>{e(t['country_name'])}</span>{detail}</div>")
        out.append(f"<div class='vstate'><h4>{e(label)} ({len(tiles)})</h4><div class='vstate-row'>{''.join(cells)}</div></div>")
    return f"<div class='vtiles-single'><div class='vtiles{' vtiles-compact' if compact else ''}'>{''.join(out)}</div></div>"


def render_lanes(rows) -> str:
    """The board's thumbnail: one line per lane, the markets in priority order (drafts)."""
    lanes: dict = {}
    for r in sorted(rows, key=lambda r: (r["lane_order"], r["priority_rank"])):
        lanes.setdefault(r["lane_label"], []).append(r["country_name"])
    return "<div class='vlanes'>" + "".join(f"<p class='vnote'><b>{e(label)}:</b> {e(', '.join(names))}</p>" for label, names in lanes.items()) + "</div>"


def render_walkthrough(rows, market: str) -> str:
    """One market's walk through the playbook, stage by stage, with the evidence file named for analysts."""
    items = "".join(f"<li><b>{e(r['stage'])}: {e(r['state_label'])}.</b> {e(r['what_happened'])}" + (f" <code>{e(r['artifact'])}</code>" if r["artifact"] else "") + "</li>"
                    for r in sorted((r for r in rows if r["country_name"] == market), key=lambda r: r["stage_order"]))
    return f"<ol class='vsteps'>{items}</ol>"


def _growth_spec(thumb):
    y = {"field": "country_name", "type": "nominal", "title": None, "sort": {"field": "growth_percent", "order": "descending"}, "axis": {"labelFontSize": 12 if thumb else 14}}
    return {"data": _src("gmp_growth"), "width": "container", "height": 200 if thumb else "container", "autosize": {"type": "fit", "contains": "padding"},
            "layer": [
                {"mark": {"type": "bar", "color": "#3D7CC9", "height": {"band": 0.6}},
                 "encoding": {"x": {"field": "growth_percent", "type": "quantitative", "title": None if thumb else "Growth since last season, same clubs (%)"}, "y": y,
                              "tooltip": [{"field": "country_name", "title": "Market"}, {"field": "growth_text", "title": "Growth"}, {"field": "direction_label", "title": "Reading"}]}},
                {"mark": {"type": "rule", "strokeDash": [4, 3], "color": "#B2182B"}, "encoding": {"x": {"field": "change_needed", "type": "quantitative"}}},
                {"mark": {"type": "rule", "strokeDash": [4, 3], "color": "#B2182B"}, "encoding": {"x": {"field": "change_needed_down", "type": "quantitative"}}}]}


def _eval_spec(thumb):
    y = {"field": "country_name", "type": "nominal", "title": None, "sort": {"field": "true_participants", "order": "descending"}, "axis": {"labelFontSize": 11 if thumb else 13}}
    x = {"field": "scenario_low", "type": "quantitative", "scale": {"type": "log"}, "title": None if thumb else "Players (log scale)"}
    return {"data": _src("gmp_eval"), "width": "container", "height": 230 if thumb else "container", "autosize": {"type": "fit", "contains": "padding"},
            "layer": [
                {"mark": {"type": "rule", "strokeWidth": 6, "strokeCap": "round", "color": "#92C5DE"}, "encoding": {"x": x, "x2": {"field": "scenario_high"}, "y": y,
                    "tooltip": [{"field": "country_name", "title": "Market"}, {"field": "scenario_low", "title": "Guess, low"}, {"field": "scenario_high", "title": "Guess, high"}]}},
                {"mark": {"type": "point", "filled": True, "size": 70},
                 "encoding": {"x": {"field": "true_participants", "type": "quantitative", "scale": {"type": "log"}}, "y": y,
                              "color": {"field": "truth_label", "type": "nominal", "title": None, "scale": {"domain": ["Inside the guess", "Above the guess", "Below the guess"], "range": ["#2166AC", "#B2182B", "#F4A582"]},
                                        "legend": None if thumb else {"orient": "bottom"}},
                              "tooltip": [{"field": "country_name", "title": "Market"}, {"field": "true_participants", "title": "True players"}, {"field": "truth_label", "title": "Truth"}]}}]}


def _trend_spec(thumb):
    return {"data": _src("gmp_trend"), "width": "container", "height": 200 if thumb else "container", "autosize": {"type": "fit", "contains": "padding"},
            "layer": [
                {"mark": {"type": "line", "point": True}, "encoding": {
                    "x": {"field": "season_year", "type": "ordinal", "title": None, "axis": {"labelAngle": 0}},
                    "y": {"field": "counting_score", "type": "quantitative", "title": None if thumb else "Counting score", "scale": {"domain": [50, 100]}},
                    "color": {"field": "country_name", "type": "nominal", "title": None, "legend": None if thumb else {"orient": "bottom"}},
                    "tooltip": [{"field": "country_name", "title": "Market"}, {"field": "season_year", "title": "Season"}, {"field": "counting_grade", "title": "Grade"},
                                {"field": "clubs_text", "title": "Clubs that sent a file"}]}},
                {"mark": {"type": "rule", "strokeDash": [4, 3], "color": "#1B2733"}, "encoding": {"y": {"field": "measured_bar", "type": "quantitative"}}}]}


def charts():
    """-> {id: chart def} for the Global outlook page: one card per question of the Phase 7 spec."""
    C = {}
    C["g1_markets"] = dict(page="global", title="Which markets can we read?", datasets=["gmp_markets"],
        card=dict(id="G1", datasets=["gmp_markets"], thumb_html=lambda d: render_markets(d["gmp_markets"]["rows"], True), open_slide=1,
                  slides=[dict(title="All 22 markets", key="ALL", html=lambda d: render_markets(d["gmp_markets"]["rows"]))]))
    C["g2_growth"] = dict(page="global", title="Is any market growing?", datasets=["gmp_growth"],
        card=dict(id="G2", datasets=["gmp_growth"], thumb=_growth_spec(True), open_slide=1, slides=[dict(title="Markets with data", key="GROWTH", spec=_growth_spec(False))]))
    C["g3_guess"] = dict(page="global", title="What would a number for a dark market have said?", datasets=["gmp_eval", "gmp_eval_summary"], evaluation=True,
        card=dict(id="G3", datasets=["gmp_eval", "gmp_eval_summary"], thumb=_eval_spec(True), open_slide=1, slides=[dict(title="Guess against truth", key="EVAL", spec=_eval_spec(False))]))
    C["g4_quality"] = dict(page="global", title="How do we make a market readable?", datasets=["gmp_trend"],
        card=dict(id="G4", datasets=["gmp_trend"], thumb=_trend_spec(True), open_slide=1, slides=[dict(title="Counting score by season", key="TREND", spec=_trend_spec(False))]))
    C["g5_next"] = dict(page="global", title="What do we do next, and how?", datasets=["gmp_board", "gmp_walkthrough"],
        card=dict(id="G5", datasets=["gmp_board", "gmp_walkthrough"], thumb_html=lambda d: render_lanes(d["gmp_board"]["rows"]), open_slide=1,
                  slides=[dict(title="The market board", key="BOARD", html=lambda d: render_board(d["gmp_board"]["rows"])),
                          dict(title="Canada, step by step", key="CANADA", html=lambda d: render_walkthrough(d["gmp_walkthrough"]["rows"], "Canada")),
                          dict(title="Italy, step by step", key="ITALY", html=lambda d: render_walkthrough(d["gmp_walkthrough"]["rows"], "Italy"))]))
    return C


PAGE_HEAD = {"global": ("Global outlook", "Where is flag football growing in the NFL's global markets, and where can't we tell?")}
PAGES = [("global", "Global outlook")]
