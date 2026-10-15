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
EVAL = {"evaluation.eval_chart_insights", "evaluation.eval_uncertainty_decomposition", "evaluation.eval_minimization_tradeoff", "demo_fix_list.scores", "demo_fix_list.nuance"}
GOVERNANCE = {"reference.privacy_params", "reference.club_market_map", "reference.funnel_step_display", "reference.p5_params", "reference.source_display", "reference.dq_dimensions", "reference.dq_grade_bands", "reference.channel_display", "reference.dq_rule_registry", "reference.dq_purposes"}

GRADES = ["A", "B", "C", "D"]
GRADE_COLORS = ["#2166ac", "#92c5de", "#f4a582", "#b2182b"]          # blue to red: separable for the common colour-vision differences, and every cell also carries its letter
PURPOSES = ["COUNT", "SEGMENT", "GEO", "RETAIN", "ACTIVATE"]
K_MIN = "(select cast(value as integer) from reference.privacy_params where param = 'k_min')"
def P5_PARAM(name):
    return f"(select cast(value as integer) from reference.p5_params where param = '{name}')"


LATEST_Q = "(select max(season_year) from quality.dq_scorecard_source)"


def _D(name, sql, relations, kind, title):
    return {"name": name, "sql": sql.strip(), "relations": set(relations), "kind": kind, "title": title}


# state tile grid (column, row) for the 14 states that have a club market; each state cell holds up to four markets in a 2 x 2 block. A layout constant, not a number computed from data.
TILE = "(values ('WA',0,0),('CA',0,2),('AZ',1,3),('CO',2,2),('TX',3,4),('IL',4,1),('OH',5,1),('PA',6,1),('NY',6,0),('NJ',7,1),('CT',7,0),('MA',8,0),('GA',5,3),('FL',6,4)) t(state, c, r)"

DATASETS = [
    _D("dq_pareto", f"""
        with k as (select cast(value as integer) as k_min from reference.privacy_params where param = 'k_min')
        select i.purpose, p.plain_label as purpose_label, i.rank_in_purpose, r.plain_label as rule_label, r.plain_action,
               case when i.impact_units >= k.k_min then round(i.impact_units, -1) end as impact_bar,
               case when i.impact_units >= k.k_min then coalesce(round(i.impact_units, -1), 0) else 0 end as impact_text_x,
               case when i.impact_units >= k.k_min then 'about ' || format('{{:,}}', cast(round(i.impact_units, -1) as bigint)) || case when i.unit = 'HOUSEHOLDS' then ' families' else ' players' end
                    else 'fewer than ' || k.k_min end as impact_label,
               case when i.impact_units >= k.k_min then format('{{:,}}', cast(round(i.impact_units, -1) as bigint)) else 'fewer than ' || k.k_min end as impact_short
        from quality.mart_dq_impact i
        join reference.dq_rule_registry r on r.rule_id = i.rule_id
        join reference.dq_purposes p on p.purpose = i.purpose
        cross join k
        where i.season_year = {LATEST_Q} and i.population = 'MODELLED' and i.rank_in_purpose <= 10 and i.impact_units > 0
        order by p.purpose, i.rank_in_purpose""", ["quality.mart_dq_impact", "quality.dq_scorecard_source", "reference.dq_rule_registry", "reference.dq_purposes", "reference.privacy_params"], "approved_aggregate",
       "Problems ranked by the players (or families) they cost, latest season, rounded to the nearest 10"),
    _D("chart_insights_club", "select chart_id, lens, field, value_display, value_raw, suppressed from share_club.share_club__chart_insights order by 1, 3", ["share_club.share_club__chart_insights"], "share_club",
       "Numbers used inside headline sentences (club share)"),
    _D("chart_insights_privacy", "select chart_id, lens, field, value_display, value_raw, suppressed from share_privacy.share_privacy__chart_insights order by 1, 3", ["share_privacy.share_privacy__chart_insights"], "share_privacy",
       "Numbers used inside headline sentences (privacy share)"),
    _D("dq_grid", f"""
        with s as (select source_system, purpose, grade, score from quality.dq_scorecard_source where season_year = {LATEST_Q} and dimension = 'PURPOSE_SCORE' and score is not null),
        act as (select source_system, score as act_score from s where purpose = 'ACTIVATE'),
        src as (select d.source_system, d.plain_name, d.source_group,
                       row_number() over (order by case when d.source_group = 'Original sources' then 0 else 1 end, coalesce(a.act_score, 101), d.plain_name) as source_rank,
                       row_number() over (order by coalesce(a.act_score, 101), d.plain_name) as worst_rank
                from reference.source_display d join act a on a.source_system = d.source_system)
        select src.plain_name as source_plain, rtrim(regexp_replace(src.plain_name, '(.{{1,24}})( |$)', '\\1' || chr(10), 'g'), chr(10)) as source_wrapped, src.source_group, src.source_rank, src.worst_rank,
               s.purpose, rtrim(regexp_replace(p.plain_label, '(.{{1,13}})( |$)', '\\1' || chr(10), 'g'), chr(10)) as purpose_wrapped, p.plain_label as purpose_label, rtrim(regexp_replace(p.plain_label, '(.{{1,22}})( |$)', '\\1' || chr(10), 'g'), chr(10)) as purpose_wrapped_wide,
               array_position(['COUNT', 'SEGMENT', 'GEO', 'RETAIN', 'ACTIVATE'], s.purpose) as purpose_order, s.grade, b.plain_label as grade_label
        from s join src on src.source_system = s.source_system join reference.dq_purposes p on p.purpose = s.purpose join reference.dq_grade_bands b on b.grade = s.grade
        order by src.source_rank, purpose_order""", ["quality.dq_scorecard_source", "reference.source_display", "reference.dq_purposes", "reference.dq_grade_bands"], "approved_aggregate",
       "Grade for each use, by source, latest season"),
    _D("dq_dims", f"""
        with scored as (select distinct source_system from quality.dq_scorecard_source where season_year = {LATEST_Q} and dimension = 'PURPOSE_SCORE' and score is not null),
        src as (select d.source_system, d.plain_name, d.source_group, row_number() over (order by case when d.source_group = 'Original sources' then 0 else 1 end, d.sort_order) as source_rank
                from reference.source_display d join scored using (source_system))
        select src.plain_name as source_plain, src.source_group, src.source_rank, p.purpose, p.plain_label as purpose_label, dm.sort_order as dimension_order,
               rtrim(regexp_replace(dm.plain_label, '(.{{1,18}})( |$)', '\\1' || chr(10), 'g'), chr(10)) as dimension_wrapped, dm.plain_label as dimension_label,
               coalesce(sc.grade, 'Not needed') as grade_or_na, coalesce(sc.grade, '\u2013') as grade_text, coalesce(b.plain_label, 'This use does not need this check') as grade_label
        from src cross join reference.dq_purposes p cross join reference.dq_dimensions dm
        left join quality.dq_scorecard_source sc on sc.source_system = src.source_system and sc.purpose = p.purpose and sc.dimension = dm.dimension and sc.season_year = {LATEST_Q} and sc.score is not null
        left join reference.dq_grade_bands b on b.grade = sc.grade
        order by p.purpose, src.source_rank, dm.sort_order""", ["quality.dq_scorecard_source", "reference.source_display", "reference.dq_purposes", "reference.dq_dimensions", "reference.dq_grade_bands"], "approved_aggregate",
       "Grade for each quality check, by source and use, latest season"),
    _D("dq_trend_lines", f"""
        with seasons as (select source_system, count(distinct season_year) as n from quality.dq_scorecard_source where dimension = 'PURPOSE_SCORE' and score is not null group by 1)
        select d.plain_name as source_plain, t.purpose, p.plain_label as purpose_label, array_position(['COUNT', 'SEGMENT', 'GEO', 'RETAIN', 'ACTIVATE'], t.purpose) as purpose_order,
               t.season_year, round(t.score, 1) as score,
               case when t.prior_seasons >= 3 then t.lcl end as lower_limit, case when t.prior_seasons >= 3 then t.ucl end as upper_limit,
               case when t.prior_seasons < 3 then 'Too early to judge' when t.out_of_control then 'Real change' else 'Normal wobble' end as status,
               t.season_year = (select max(season_year) from quality.dq_trend) as is_latest
        from quality.dq_trend t join seasons s on s.source_system = t.entity_id and s.n >= 4
        join reference.source_display d on d.source_system = t.entity_id join reference.dq_purposes p on p.purpose = t.purpose
        where t.entity_type = 'SOURCE'
        order by purpose_order, d.sort_order, t.season_year""", ["quality.dq_trend", "quality.dq_scorecard_source", "reference.source_display", "reference.dq_purposes"], "approved_aggregate",
       "Source quality over the seasons with normal-wobble limits (provisional method)"),
    _D("dq_org_grades", f"""
        with o as (
            select c.plain_name as channel_plain, c.sort_order as channel_order, o.grade,
                   case when o.record_count < {P5_PARAM('size_band_small_below')} then 'Small leagues' when o.record_count >= {P5_PARAM('size_band_large_from')} then 'Large leagues' else 'Medium leagues' end as size_label
            from quality.dq_scorecard_org o join reference.channel_display c on c.channel = o.channel
            where o.season_year = {LATEST_Q} and o.purpose = 'SEGMENT' and o.dimension = 'PURPOSE_SCORE' and o.reported and o.score is not null),
        g as (select 'League size' as group_kind, size_label as group_label, case size_label when 'Small leagues' then 1 when 'Medium leagues' then 2 else 3 end as group_order, grade from o
              union all select 'How the league sends data', channel_plain, channel_order, grade from o),
        n as (select group_kind, group_label, group_order, count(*) as group_n from g group by all),
        c as (select group_kind, group_label, group_order, grade, count(*) as k from g group by all)
        select c.group_kind, c.group_label, c.group_order, c.grade, b.plain_label as grade_label, round(100.0 * c.k / n.group_n, 1) as share_pct,
               cast(round(100.0 * c.k / n.group_n) as bigint) || '% of ' || lower(c.group_label) as share_label, 'Leagues graded' as measure
        from c join n using (group_kind, group_label, group_order) join reference.dq_grade_bands b on b.grade = c.grade
        where n.group_n >= {K_MIN}
        order by c.group_kind desc, c.group_order, c.grade""", ["quality.dq_scorecard_org", "quality.dq_scorecard_source", "reference.channel_display", "reference.dq_grade_bands", "reference.privacy_params", "reference.p5_params"], "approved_aggregate",
       "Share of leagues at each grade for splitting players by age and gender, by league size and by how the league sends data"),
    _D("dq_org_scatter", f"""
        select c.plain_name as channel_plain, o.record_count, round(o.score, 1) as score, round(o.score_interval_low, 1) as score_interval_low, round(o.score_interval_high, 1) as score_interval_high, o.grade
        from quality.dq_scorecard_org o join reference.channel_display c on c.channel = o.channel
        where o.season_year = {LATEST_Q} and o.purpose = 'SEGMENT' and o.dimension = 'PURPOSE_SCORE' and o.reported and o.score is not null
        order by o.record_count""", ["quality.dq_scorecard_org", "quality.dq_scorecard_source", "reference.channel_display"], "approved_aggregate", "League score against league size, latest season"),
    _D("dq_fix_examples", f"""
        with f as (
            select f.org_id, f.rule_id, f.rank_in_scope, f.impact_estimate, f.impact_unit, f.impact_basis, f.purposes_breached
            from quality.dq_fix_list f where f.season_year = {LATEST_Q} and not f.is_systemic and f.rank_in_scope <= 3),
        chan as (select distinct org_id, channel from quality.dq_scorecard_org),
        per_org as (select org_id, count(*) as n_fixes, sum(impact_estimate) as total from f group by 1),
        a as (select f.org_id from f join chan using (org_id) join per_org using (org_id) where chan.channel = 'SPREADSHEET' group by f.org_id, per_org.n_fixes, per_org.total order by per_org.n_fixes desc, per_org.total desc, f.org_id limit 1),
        b as (select f.org_id from f join per_org using (org_id) where f.rank_in_scope = 1 and f.rule_id = 'DQ-TIME-ORG-REPORTED' and f.org_id not in (select org_id from a) order by f.impact_estimate desc, f.org_id limit 1),
        c as (select f.org_id from f join per_org using (org_id) where f.rule_id like 'DQ-PROV-%' and per_org.n_fixes >= 2 and f.org_id not in (select org_id from a union select org_id from b)
              group by f.org_id, per_org.total order by per_org.total desc, f.org_id limit 1),
        picked as (select 1 as example_no, 'League A (made-up name)' as league_label, 'Sends spreadsheets' as profile_label, org_id from a
                   union all select 2, 'League B (made-up name)', 'Late or missing file', org_id from b
                   union all select 3, 'League C (made-up name)', 'Consent form gaps', org_id from c),
        why as (select f.org_id, f.rule_id, string_agg(lower(p.plain_label), ', ' order by p.purpose) as uses
                from f cross join unnest(f.purposes_breached) as u(purpose) join reference.dq_purposes p on p.purpose = u.purpose group by 1, 2)
        select pk.example_no, pk.league_label, pk.profile_label, f.rank_in_scope as fix_no, r.plain_label, r.plain_action,
               'So that it works for: ' || w.uses || '.' as why,
               case when f.impact_estimate < {K_MIN} then 'fewer than ' || {K_MIN} || (case when f.impact_unit = 'HOUSEHOLDS' then ' families' else ' players' end)
                    else 'about ' || cast(round(f.impact_estimate, -1) as bigint) || (case when f.impact_unit = 'HOUSEHOLDS' then ' families' else ' players' end) end
               || (case when f.impact_basis = 'MEASURED' then '' else ' (estimated)' end) as scale_text,
               f.rule_id = 'DQ-TIME-ORG-REPORTED' as is_no_file
        from picked pk join f using (org_id) join reference.dq_rule_registry r on r.rule_id = f.rule_id join why w on w.org_id = f.org_id and w.rule_id = f.rule_id
        order by pk.example_no, f.rank_in_scope""", ["quality.dq_fix_list", "quality.dq_scorecard_org", "quality.dq_scorecard_source", "reference.dq_rule_registry", "reference.dq_purposes", "reference.privacy_params"], "approved_aggregate",
       "Example fix lists for three made-up leagues, one per quality profile"),
    _D("unc_decomp", """
        select participation_year, component,
               case component when 'IDENTITY' then 'Matching people' when 'DQ_EXCLUSIONS' then 'Records that fail the rules' else 'Leagues that sent no file' end as component_label,
               case component when 'IDENTITY' then 1 when 'DQ_EXCLUSIONS' then 2 else 3 end as component_order,
               round(reported_point, -1) as reported_point, round(interval_low, -1) as interval_low, round(interval_high, -1) as interval_high
        from quality.mart_uncertainty_decomposition order by participation_year, component""", ["quality.mart_uncertainty_decomposition"], "approved_aggregate",
       "Participants counted, with three separate uncertainty intervals"),
    _D("miss_dumbbell", f"""
        select participation_year, segment_value as division, round(100 * value_known_only, 1) as girls_pct, round(100 * bound_low, 1) as bound_low_pct, round(100 * bound_high, 1) as bound_high_pct, unknown, total
        from quality.mart_missingness_bias
        where kpi = 'girls_share_of_youth' and club_market_id = 'ALL' and segment_value <> 'ALL' and total >= {K_MIN}
        order by participation_year, segment_value""", ["quality.mart_missingness_bias", "reference.privacy_params"], "approved_aggregate",
       "Girls' share of youth by division: known-only value and the bounds when unknown genders are assigned either way"),
    _D("unc_truth", """
        select participation_year, 'Matching people' as component, round(identity_low, -1) as low, round(identity_high, -1) as high, round(true_participants_in_data, -1) as truth,
               identity_interval_contains_truth as truth_inside
        from evaluation.eval_uncertainty_decomposition
        union all
        select participation_year, 'Records that fail the rules', round(dq_strict, -1), round(dq_lenient, -1), round(true_participants_in_data, -1), true_participants_in_data between dq_strict and dq_lenient
        from evaluation.eval_uncertainty_decomposition
        union all
        select participation_year, 'Leagues that sent no file', round(identity_point + coverage_low, -1), round(identity_point + coverage_high, -1), round(true_total_participants, -1),
               true_total_participants between identity_point + coverage_low and identity_point + coverage_high
        from evaluation.eval_uncertainty_decomposition
        order by 1, 2""", ["evaluation.eval_uncertainty_decomposition"], "evaluation", "Each uncertainty component against the synthetic truth"),
    _D("fix_demo_scores", "select org_group, purpose, orgs_scored, score_before, score_after from demo_fix_list.scores order by org_group, purpose", ["demo_fix_list.scores"], "evaluation",
       "SIMULATED: purpose scores of organizations that acted on a fix list, before and after"),
    _D("fix_demo_nuance", "select measure, value_before, value_after from demo_fix_list.nuance order by measure", ["demo_fix_list.nuance"], "evaluation",
       "SIMULATED: what the fix list does to the nuance layer"),
    # ---- club markets (share_club only) ----
    _D("market_tiles", f"""
        with y as (select max(participation_year) as y from share_club.share_club__market_year),
        mk as (select club_market_id, any_value(plain_name) as plain_name, any_value(state) as state from reference.club_market_map where regexp_matches(club_market_id, '^CM-') group by 1),
        m as (select s.* from share_club.share_club__market_year s, y where s.participation_year = y.y and regexp_matches(s.club_market_id, '^CM-')),
        p as (select purpose, plain_label, array_position(['COUNT', 'SEGMENT', 'GEO', 'RETAIN', 'ACTIVATE'], purpose) as purpose_order from reference.dq_purposes)
        select mk.club_market_id, mk.plain_name, regexp_replace(mk.plain_name, ' market [0-9]+$', '') as state_name,
               array_position(['WA', 'CA', 'AZ', 'CO', 'TX', 'IL', 'OH', 'PA', 'NY', 'NJ', 'CT', 'MA', 'GA', 'FL'], mk.state) as state_order, cast(right(mk.club_market_id, 2) as integer) as market_no,
               p.purpose, p.plain_label as purpose_label, p.purpose_order,
               case when m.club_market_id is null then 'No data yet' when m.suppressed <> 'NONE' then 'Hidden' else 'Graded' end as status,
               case p.purpose when 'COUNT' then m.grade_count when 'SEGMENT' then m.grade_segment when 'GEO' then m.grade_geo when 'RETAIN' then m.grade_retain else m.grade_activate end as grade,
               case when m.club_market_id is null then 'No data yet' when m.suppressed <> 'NONE' then 'fewer than ' || {K_MIN} || ' players'
                    else 'about ' || format('{{:,}}', cast(round(m.participants_allocated, -1) as bigint)) || ' players' end as players_text,
               case when m.club_market_id is null then '' when coalesce(m.orgs_known, 0) = 0 then 'No leagues known yet'
                    else cast(cast(m.orgs_reporting as bigint) as varchar) || ' of ' || cast(cast(m.orgs_known as bigint) as varchar) || ' leagues reporting' end as leagues_text
        from mk cross join p left join m on m.club_market_id = mk.club_market_id
        order by p.purpose_order, state_order, market_no""", ["share_club.share_club__market_year", "reference.club_market_map", "reference.dq_purposes", "reference.privacy_params"], "share_club",
       "Club-market tiles: grade for each use, players and leagues reporting, latest season (all markets, including those with no data yet)"),
    _D("market_growth", f"""
        with s as (select club_market_id, participation_year, participants_allocated as p, participants_allocated_interval_low as lo, participants_allocated_interval_high as hi
                   from share_club.share_club__market_year where regexp_matches(club_market_id, '^CM-') and suppressed = 'NONE'),
        base as (select club_market_id, arg_min(p, participation_year) as p0, min(participation_year) as first_year, arg_max(p, participation_year) as p_latest from s group by 1),
        ranked as (select club_market_id, row_number() over (order by p_latest desc, club_market_id) as rnk from base)
        select (select any_value(plain_name) from reference.club_market_map c where c.club_market_id = s.club_market_id) as plain_name, s.participation_year,
               cast(round(100.0 * s.p / b.p0) as bigint) as growth_index, cast(round(100.0 * s.lo / b.p0) as bigint) as index_low, cast(round(100.0 * s.hi / b.p0) as bigint) as index_high,
               b.first_year, (r.rnk - 1) // 6 + 1 as slide_no, r.rnk as size_rank
        from s join base b using (club_market_id) join ranked r using (club_market_id)
        order by r.rnk, s.participation_year""", ["share_club.share_club__market_year", "reference.club_market_map"], "share_club",
       "Players per club market since its first year (first year = 100), with the range that allows for leagues that sent no data"),
    _D("market_funnel", f"""
        with y as (select max(participation_year) as y from share_club.share_club__activation_funnel),
        top6 as (select club_market_id, row_number() over (order by participants_allocated desc, club_market_id) as slide_no
                 from share_club.share_club__market_year where regexp_matches(club_market_id, '^CM-') and suppressed = 'NONE'
                   and participation_year = (select max(participation_year) from share_club.share_club__market_year) qualify slide_no <= 6),
        keys as (select 'ALL' as club_market_id, 'All club markets' as slide_title, 0 as slide_no
                 union all select t.club_market_id, (select any_value(plain_name) from reference.club_market_map c where c.club_market_id = t.club_market_id), t.slide_no from top6 t),
        f as (select k.club_market_id, k.slide_title, k.slide_no, d.display_no, d.plain_name as step_name, d.plain_unit,
                     round(f.funnel_count, -1) as r, round(coalesce(f.funnel_lost_dq, 0), -1) as dq, round(coalesce(f.funnel_lost_privacy, 0), -1) as pr
              from share_club.share_club__activation_funnel f join keys k on k.club_market_id = f.club_market_id join y on f.participation_year = y.y
              join reference.funnel_step_display d on d.step_no = f.step_no where f.funnel_count is not null),
        big as (select slide_no, max(r) as top from f group by 1),
        seg as (
            select f.slide_no, f.slide_title, f.display_no, f.step_name, f.plain_unit, 'Still reachable' as part, 1 as part_order, 0.0 as x0, f.r as x1, f.r as amount, big.top from f join big using (slide_no)
            union all select f.slide_no, f.slide_title, f.display_no, f.step_name, f.plain_unit, 'Fixable data problem', 2, f.r, f.r + f.dq, f.dq, big.top from f join big using (slide_no) where f.dq > 0
            union all select f.slide_no, f.slide_title, f.display_no, f.step_name, f.plain_unit, 'Family''s choice or never asked', 3, f.r + f.dq, f.r + f.dq + f.pr, f.pr, big.top from f join big using (slide_no) where f.pr > 0)
        select slide_no, slide_title, display_no, step_name, part, part_order, x0, x1, (x0 + x1) / 2 as x_mid,
               case when amount < {K_MIN} then 'fewer than ' || {K_MIN} else 'about ' || format('{{:,}}', cast(amount as bigint)) end as amount_label,
               case when amount >= 0.04 * top then format('{{:,}}', cast(amount as bigint)) else '' end as bar_label, plain_unit as unit
        from seg order by slide_no, display_no, part_order""", ["share_club.share_club__activation_funnel", "share_club.share_club__market_year", "reference.club_market_map", "reference.funnel_step_display", "reference.privacy_params"], "share_club",
       "Players and families remaining at each step, and what was lost, nationally and for the six largest markets"),
    _D("market_orgs", """
        with y as (select max(participation_year) as y from share_club.share_club__market_year),
        m as (select s.club_market_id, cast(s.orgs_reporting as bigint) as sent, cast(s.orgs_dark as bigint) as dark, cast(s.orgs_known as bigint) as known
              from share_club.share_club__market_year s, y where s.participation_year = y.y and regexp_matches(s.club_market_id, '^CM-') and s.suppressed = 'NONE' and s.orgs_known > 0),
        r as (select *, row_number() over (order by 1.0 * dark / known desc, known desc, club_market_id) as rnk from m)
        select (select any_value(plain_name) from reference.club_market_map c where c.club_market_id = r.club_market_id) as plain_name, r.rnk as dark_rank, (r.rnk - 1) // 12 + 1 as slide_no,
               p.part, p.part_order, case when p.part_order = 1 then 0.0 else 100.0 * r.sent / r.known end as x0, case when p.part_order = 1 then 100.0 * r.sent / r.known else 100.0 end as x1,
               cast(r.sent as varchar) || ' of ' || cast(r.known as varchar) || ' leagues sent data' as leagues_text, 100.0 as label_x
        from r cross join (values ('Sent data', 1), ('Sent no data', 2)) p(part, part_order)
        where p.part_order = 1 or r.dark > 0
        order by r.rnk, p.part_order""", ["share_club.share_club__market_year", "reference.club_market_map"], "share_club", "Leagues known in each club market that sent data and that sent none, latest season"),
    _D("market_no_leagues", """
        with y as (select max(participation_year) as y from share_club.share_club__market_year),
        known as (select s.club_market_id from share_club.share_club__market_year s, y where s.participation_year = y.y and s.orgs_known > 0 and s.club_market_id is not null)
        select any_value(plain_name) as plain_name, club_market_id from reference.club_market_map where regexp_matches(club_market_id, '^CM-') and club_market_id not in (select club_market_id from known)
        group by club_market_id order by club_market_id""", ["share_club.share_club__market_year", "reference.club_market_map"], "share_club", "Club markets with no known league yet"),
    _D("market_pairs", f"""
        with y as (select max(participation_year) as y from share_club.share_club__market_year),
        top6 as (select s.*, row_number() over (order by s.participants_allocated desc, s.club_market_id) as slide_no
                 from share_club.share_club__market_year s, y where s.participation_year = y.y and regexp_matches(s.club_market_id, '^CM-') and s.suppressed = 'NONE' qualify slide_no <= 6),
        fun as (select f.club_market_id, f.step_no, f.funnel_count from share_club.share_club__activation_funnel f where f.participation_year = (select y from y)),
        fam as (select club_market_id, max(funnel_count) filter (where step_no = 3) as families, max(funnel_count) filter (where step_no = 5) as known_consent, max(funnel_count) filter (where step_no = 6) as reachable from fun group by 1)
        select t.slide_no, (select any_value(plain_name) from reference.club_market_map c where c.club_market_id = t.club_market_id) as plain_name,
               'about ' || format('{{:,}}', cast(round(t.participants_allocated, -1) as bigint)) || ' players' as players_text,
               case when t.participants_allocated_interval_high > t.participants_allocated_interval_low
                    then 'between ' || format('{{:,}}', cast(round(t.participants_allocated_interval_low, -1) as bigint)) || ' and ' || format('{{:,}}', cast(round(t.participants_allocated_interval_high, -1) as bigint)) || ' once leagues that sent no data are allowed for' else '' end as range_text,
               cast(cast(t.orgs_reporting as bigint) as varchar) || ' of ' || cast(cast(t.orgs_known as bigint) as varchar) || ' leagues reporting' as leagues_text,
               case when f.reachable is null or f.families is null then 'fewer than ' || {K_MIN} || ' families' else 'about ' || format('{{:,}}', cast(round(f.reachable, -1) as bigint)) || ' of about ' || format('{{:,}}', cast(round(f.families, -1) as bigint)) || ' families can be contacted by the club' end as reach_text,
               case when f.known_consent is null or f.families is null then 'fewer than ' || {K_MIN} || ' families' else 'about ' || format('{{:,}}', cast(round(f.known_consent, -1) as bigint)) || ' of about ' || format('{{:,}}', cast(round(f.families, -1) as bigint)) || ' families have a consent record we can read' end as consent_text,
               'The club receives counts only, and the smallest count shown is {{K_MIN_TEXT}}.' as receives_text
        from top6 t left join fam f on f.club_market_id = t.club_market_id
        order by t.slide_no""".replace("{K_MIN_TEXT}", "' || " + K_MIN + " || '"), ["share_club.share_club__market_year", "share_club.share_club__activation_funnel", "reference.club_market_map", "reference.privacy_params"], "share_club",
       "The six largest club markets, as the club sees them and as the privacy lead sees them"),
    _D("market_pair_grades", """
        with y as (select max(participation_year) as y from share_club.share_club__market_year),
        top6 as (select s.*, row_number() over (order by s.participants_allocated desc, s.club_market_id) as slide_no
                 from share_club.share_club__market_year s, y where s.participation_year = y.y and regexp_matches(s.club_market_id, '^CM-') and s.suppressed = 'NONE' qualify slide_no <= 6),
        g as (select slide_no, 'COUNT' as purpose, grade_count as grade from top6 union all select slide_no, 'SEGMENT', grade_segment from top6 union all select slide_no, 'GEO', grade_geo from top6
              union all select slide_no, 'RETAIN', grade_retain from top6 union all select slide_no, 'ACTIVATE', grade_activate from top6)
        select g.slide_no, p.plain_label as purpose_label, array_position(['COUNT', 'SEGMENT', 'GEO', 'RETAIN', 'ACTIVATE'], g.purpose) as purpose_order, g.grade, b.plain_label as grade_label
        from g join reference.dq_purposes p on p.purpose = g.purpose join reference.dq_grade_bands b on b.grade = g.grade order by g.slide_no, purpose_order""",
       ["share_club.share_club__market_year", "reference.dq_purposes", "reference.dq_grade_bands"], "share_club", "Grades for each use in the six largest club markets"),
    # ---- privacy ----
    _D("frontier", """
        select variant_id, case variant_id when 'V0_FULL' then 'Full birth date and ZIP code' when 'V1_BIRTH_MONTH' then 'Birth month, full ZIP code' when 'V2_BIRTH_YEAR' then 'Birth year, 3-digit ZIP, email and phone' when 'V3_NO_PHONE' then 'Birth year, 3-digit ZIP, email only' when 'V4_HASHED_CONTACT' then 'Birth year, 3-digit ZIP, hashed email' else label end as short_label, label as variant_label, in_standard, pct_unique, pct_rows_below_k_min, precision, recall, f1, sibling_or_twin_false_merges, participant_count_error_pct, fit_for_activate, contact_fields_held
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
        select s.source_system, s.consent_text_version, case s.provenance_grade when 'KNOWN_FULL' then 'Fully recorded' when 'KNOWN_PARTIAL' then 'Partly recorded' else 'Not recorded' end as provenance_label,
               s.provenance_grade, s.consent_events, s.suppressed, s.x0, s.x0 + coalesce(s.consent_events, 0) as x1,
               coalesce(d.plain_name, s.source_system) || ' \u00b7 ' || case s.consent_text_version when 'v1_ops_only' then 'form 1 (league operations only)' when 'v2_ops_photo' then 'form 2 (adds photos)'
                    when 'v3_ops_comms' then 'form 3 (adds league messages)' else 'form 4 (adds club marketing)' end as form
        from s left join reference.source_display d on d.source_system = s.source_system order by s.source_system, s.consent_text_version, s.provenance_grade""", ["share_privacy.share_privacy__consent_provenance", "reference.source_display"], "share_privacy",
       "Consent events by provenance grade, source and consent text version, latest season"),
    _D("purpose_matrix", "select case consent_text_version when 'v1_ops_only' then 'Form 1 (league operations only)' when 'v2_ops_photo' then 'Form 2 (adds photos)' when 'v3_ops_comms' then 'Form 3 (adds league messages)' else 'Form 4 (adds club marketing)' end as form, "
       "consent_text_version, purpose, purpose_label, form_names_purpose, separate_consent_required, "
       "case when form_names_purpose then 'Named on the form' else 'Not named' end as coverage, case when form_names_purpose then 'yes' else 'no' end as mark "
       "from share_privacy.share_privacy__purpose_coverage order by consent_text_version, purpose",
       ["share_privacy.share_privacy__purpose_coverage"], "share_privacy", "Which purposes each consent wording names"),
    _D("retention_del", """
        select metric_label, 'Rebuilt from anonymized facts' as scenario, coalesce(facts_only_change, 0) as change, survives_facts_only as survives from share_privacy.share_privacy__retention_vs_deletion
        where baseline > 0
        union all
        select metric_label, 'Identity re-run on anonymized inputs', coalesce(identity_rebuilt_change, 0), survives_identity_rebuilt from share_privacy.share_privacy__retention_vs_deletion where baseline > 0
        order by 1, 2""", ["share_privacy.share_privacy__retention_vs_deletion"], "share_privacy", "Change in each retention figure after the age-out deletion"),
    _D("chart_insights_eval", "select chart_id, lens, field, value_display, value_raw, suppressed from evaluation.eval_chart_insights order by 1, 3", ["evaluation.eval_chart_insights"], "evaluation",
       "Numbers used inside headline sentences (evaluation cards)"),
    _D("analyst_k", "select participation_year, participant_years, equivalence_classes, smallest_class, average_class_size, pct_unique, pct_rows_below_k_warn, pct_rows_below_k_min "
       "from share_privacy.share_privacy__analyst_k_anonymity order by 1", ["share_privacy.share_privacy__analyst_k_anonymity"], "share_privacy", "How identifying the analyst share is, per year"),
    _D("policy_results", "select check_name, violations from share_privacy.share_privacy__policy_checks order by 1", ["share_privacy.share_privacy__policy_checks"], "share_privacy", "Share-policy check results"),
]

VALUE_LABELS = {
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
    "pct_rows_below_k_warn": "Below warning size (%)", "check_name": "Check", "violations": "Violations", "participants_allocated_label": "Participants", "plain_action": "What to do", "rule_label": "Problem", "impact_bar": "Affected (rounded)", "impact_text_x": "Label position", "impact_label": "Affected", "impact_short": "Label", "short_label": "Fields kept", "label_x": "Label position", "x_mid": "Label position", "bar_label": "Label", "amount_label": "Amount", "players_text": "Players", "leagues_text": "Leagues", "range_text": "Range", "reach_text": "Reach", "consent_text": "Consent", "receives_text": "What the club receives", "growth_index": "Index (first year = 100)", "index_low": "Range from", "index_high": "Range to", "slide_title": "Slide", "step_name": "Step", "state_name": "State", "market_no": "Market no.", "state_order": "State order", "dark_rank": "Rank", "slide_no": "Slide", "size_rank": "Size rank", "first_year": "First year", "display_no": "Step no.", "part_order": "Order", "part": "Part", "unit": "Unit", "plain_name": "Market", "status": "Reading", "source_plain": "Source", "purpose_wrapped": "Use", "purpose_wrapped_wide": "Use", "source_wrapped": "Source", "worst_rank": "Rank (worst first)", "source_rank": "Order", "grade_label": "Meaning", "grade_or_na": "Grade", "grade_text": "Grade", "dimension_label": "Check", "dimension_wrapped": "Check", "dimension_order": "Order", "purpose_order": "Order", "source_group": "Group", "lower_limit": "Normal range from", "upper_limit": "to", "status": "Reading", "group_kind": "Group kind", "group_label": "Group", "group_order": "Order", "share_pct": "Share (%)", "share_label": "Share", "measure": "Measure", "channel_plain": "How it sends data", "league_label": "League", "profile_label": "Profile", "fix_no": "Fix", "plain_label": "Problem", "why": "Why", "scale_text": "Scale", "is_no_file": "No file sent", "example_no": "Example", "is_latest": "Latest season",
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
    # Q1 and Q2 are built after Q3 below (cards)
    def pareto_spec(use, top, height, thumb):
        bar_x = {"field": "impact_bar", "type": "quantitative", "title": None if thumb else "Players or families affected (about)", "axis": {"tickMinStep": 1, "format": "d", "tickCount": 3 if thumb else 6}}
        y = {"field": "rule_label", "type": "nominal", "sort": {"field": "rank_in_purpose", "op": "min"}, "title": None, "axis": {"labelLimit": 320, "labelFontSize": 12 if thumb else 14}}
        return {"data": _src("dq_pareto"), "width": "container", "height": height, "autosize": {"type": "fit", "contains": "padding"}, "padding": {"left": 4, "right": 64, "top": 4, "bottom": 4},
                "transform": [{"filter": f"datum.purpose === '{use}' && datum.rank_in_purpose <= {top}"}],
                "layer": [
                    {"mark": {"type": "bar", "clip": True, "color": "#3D7CC9", "height": {"band": 0.7}}, "encoding": {"x": bar_x, "y": y,
                        "tooltip": [{"field": "rule_label", "title": "Problem"}, {"field": "plain_action", "title": "What to do"}, {"field": "impact_label", "title": "Affected"}]}},
                    {"mark": {"type": "text", "align": "left", "dx": 4, "fontSize": 12 if thumb else 13}, "encoding": {"x": {"field": "impact_text_x", "type": "quantitative"}, "y": y,
                        "text": {"field": "impact_short", "type": "nominal"}, "color": {"value": "#1B2733"}}}]}

    uses = [("COUNT", "Counting players"), ("SEGMENT", "Breaking down by age and gender"), ("GEO", "Placing players on the map"), ("RETAIN", "Tracking who comes back"), ("ACTIVATE", "Contacting families")]
    C["q3_pareto"] = dict(
        page="quality", title="Which few fixes matter most?", datasets=["dq_pareto"],
        card=dict(id="Q3", datasets=["dq_pareto"], thumb=pareto_spec("ACTIVATE", 6, 230, True), open_slide=5,
                  slides=[dict(title=label, key=use, spec=pareto_spec(use, 10, "container", False)) for use, label in uses]))
    C.update(quality_cards())
    C.update(market_cards())
    C.update(sure_cards())
    C.update(privacy_cards())
    order = ["q1_grid", "q2_trend", "q3_pareto", "q4_size", "q5_fix", "p3_frontier", "p1_provenance", "p2_matrix", "p4_retention", "p5_kanon"]
    C = {**{k: C[k] for k in order if k in C}, **{k: v for k, v in C.items() if k not in order}}
    return C


GRADE_TEXT = {"condition": {"test": "datum.grade === 'A' || datum.grade === 'D'", "value": "#ffffff"}, "value": "#000000"}
GRADE_DOMAIN_NA = {"domain": GRADES + ["Not needed"], "range": GRADE_COLORS + ["#d9d9d9"]}
SIZE = {"autosize": {"type": "fit", "contains": "padding"}, "width": "container"}


def _purpose_axis(thumb):
    return {"field": "purpose_label", "type": "nominal", "title": None, "sort": {"field": "purpose_order", "op": "min"}, "axis": None}


def _col_headers(x_field, text_field, order_field, rank_field, size, lines):
    """Column headers as a text layer so they can wrap (axis labels cannot): drawn once, from the first row of each column, above the plot."""
    return {"transform": [{"filter": f"datum.{rank_field} === 1"}],
            "mark": {"type": "text", "lineBreak": "\n", "baseline": "top", "dy": -(lines * (size + 3) + 6), "fontSize": size, "lineHeight": size + 3, "clip": False},
            "encoding": {"x": {"field": x_field, "type": "nominal", "title": None, "sort": {"field": order_field, "op": "min"}, "axis": None},
                         "y": {"value": 0}, "text": {"field": text_field, "type": "nominal"}, "color": {"value": "#4A5866"}}}


def _grid_spec(thumb):
    """Sources down, the five uses across; each cell is the grade as a letter on a colour. The thumbnail keeps the six worst sources for contacting families."""
    y = {"field": "source_plain", "type": "nominal", "title": None, "sort": {"field": "worst_rank" if thumb else "source_rank", "op": "min"},
         "axis": {"labelLimit": 400, "labelFontSize": 11 if thumb else 14, "labelPadding": 6}}
    layers = [
        {"mark": {"type": "rect", "stroke": "#ffffff", "strokeWidth": 2, "clip": True}, "encoding": {"x": _purpose_axis(thumb), "y": y,
            "color": {"field": "grade", "type": "nominal", "scale": GRADE_SCALE, "legend": None if thumb else {"title": "Grade", "orient": "bottom", "direction": "horizontal"}},
            "tooltip": [{"field": "source_plain", "title": "Source"}, {"field": "purpose_label", "title": "Use"}, {"field": "grade", "title": "Grade"}, {"field": "grade_label", "title": "Meaning"}]}},
        {"mark": {"type": "text", "fontSize": 13 if thumb else 20, "fontWeight": "bold", "clip": True}, "encoding": {"x": _purpose_axis(thumb), "y": y, "text": {"field": "grade", "type": "nominal"}, "color": GRADE_TEXT}},
        _col_headers("purpose_label", "purpose_wrapped" if thumb else "purpose_wrapped_wide", "purpose_order", "worst_rank" if thumb else "source_rank", 11 if thumb else 14, 3 if thumb else 2)]
    spec = {"data": _src("dq_grid"), **SIZE, "padding": {"left": 4, "right": 8, "top": 52 if thumb else 44, "bottom": 4 if thumb else 36}, "layer": layers}
    spec["height"] = "container"
    if thumb:
        spec["transform"] = [{"filter": "datum.worst_rank <= 6"}]
    return spec


def _dims_spec(use):
    x = {"field": "dimension_label", "type": "nominal", "title": None, "sort": {"field": "dimension_order", "op": "min"}, "axis": None}
    y = {"field": "source_plain", "type": "nominal", "title": None, "sort": {"field": "source_rank", "op": "min"}, "axis": {"labelLimit": 400, "labelFontSize": 13, "labelPadding": 6}}
    return {"data": _src("dq_dims"), **SIZE, "height": "container", "padding": {"left": 4, "right": 8, "top": 44, "bottom": 36},
            "transform": [{"filter": f"datum.purpose === '{use}'"}],
            "layer": [
                {"mark": {"type": "rect", "stroke": "#ffffff", "strokeWidth": 2, "clip": True}, "encoding": {"x": x, "y": y,
                    "color": {"field": "grade_or_na", "type": "nominal", "scale": GRADE_DOMAIN_NA, "legend": {"title": "Grade", "orient": "bottom", "direction": "horizontal", "labelLimit": 300}},
                    "tooltip": [{"field": "source_plain", "title": "Source"}, {"field": "dimension_label", "title": "Check"}, {"field": "grade_label", "title": "Meaning"}]}},
                {"mark": {"type": "text", "fontSize": 16, "fontWeight": "bold", "clip": True}, "encoding": {"x": x, "y": y, "text": {"field": "grade_text", "type": "nominal"},
                    "color": {"condition": {"test": "datum.grade_or_na === 'A' || datum.grade_or_na === 'D'", "value": "#ffffff"}, "value": "#000000"}}},
                _col_headers("dimension_label", "dimension_wrapped", "dimension_order", "source_rank", 12, 2)]}


def _trend_spec(use, thumb):
    """One line per source with its normal-wobble band. Seasons with fewer than three earlier ones carry no band and read 'too early to judge'."""
    xe = {"field": "season_year", "type": "ordinal", "title": None, "axis": {"labelAngle": 0, "labelFontSize": 11 if thumb else 13}}
    ye = {"field": "score", "type": "quantitative", "title": "Quality score" if not thumb else None, "scale": {"zero": False}, "axis": {"tickCount": 4 if thumb else 8, "format": "d"}}
    col = {"field": "source_plain", "type": "nominal", "title": None, "legend": {"orient": "top", "labelLimit": 500, "columns": 2 if thumb else 3, "symbolLimit": 0, "labelFontSize": 11 if thumb else 13}}
    dash = {"field": "source_plain", "type": "nominal", "legend": None}
    status = {"field": "status", "type": "nominal", "title": None, "scale": {"domain": ["Normal wobble", "Real change", "Too early to judge"], "range": ["circle", "diamond", "triangle-up"]},
              "legend": {"orient": "bottom", "labelLimit": 300, "symbolFillColor": "transparent", "symbolStrokeColor": "#555555", "title": "Reading", "direction": "horizontal"}}
    return {"data": _src("dq_trend_lines"), **SIZE, "height": "container", "padding": {"left": 4, "right": 8, "top": 4, "bottom": 4},
            "transform": [{"filter": f"datum.purpose === '{use}'"}],
            "layer": [
                {"mark": {"type": "area", "opacity": 0.12, "clip": True}, "encoding": {"x": xe, "y": {"field": "lower_limit", "type": "quantitative", "scale": {"zero": False}}, "y2": {"field": "upper_limit"}, "color": {**col, "legend": None}}},
                {"mark": {"type": "line", "clip": True, "strokeWidth": 2}, "encoding": {"x": xe, "y": ye, "color": col, "strokeDash": dash}},
                {"mark": {"type": "point", "filled": True, "size": 70 if thumb else 110, "clip": True, "strokeWidth": 2}, "encoding": {"x": xe, "y": ye, "color": col, "shape": status,
                    "tooltip": [{"field": "source_plain", "title": "Source"}, {"field": "season_year", "title": "Season"}, {"field": "score", "title": "Score"}, {"field": "status", "title": "Reading"},
                                {"field": "lower_limit", "title": "Normal range from"}, {"field": "upper_limit", "title": "to"}]}}]}


def _size_spec(thumb):
    """Share of leagues at each grade, as 100% bars, by league size and by how the league sends data."""
    return {"data": _src("dq_org_grades"), **SIZE, "height": "container", "padding": {"left": 4, "right": 8, "top": 4, "bottom": 4},
            "mark": {"type": "bar", "clip": True, "height": {"band": 0.75}, "stroke": "#ffffff", "strokeWidth": 1},
            "encoding": {"y": {"field": "group_label", "type": "nominal", "title": None, "sort": {"field": "group_order", "op": "min"}, "axis": {"labelLimit": 400, "labelFontSize": 12 if thumb else 14}},
                         "x": {"field": "share_pct", "type": "quantitative", "title": None if thumb else "Share of leagues (%)", "scale": {"domain": [0, 100]}, "axis": {"tickCount": 5, "format": "d"}},
                         "color": {"field": "grade", "type": "nominal", "scale": GRADE_SCALE, "legend": {"title": "Grade", "orient": "top", "direction": "horizontal"}, "sort": GRADES},
                         "order": {"field": "grade", "type": "nominal", "sort": "descending"},
                         "tooltip": [{"field": "group_label", "title": "Group"}, {"field": "grade", "title": "Grade"}, {"field": "grade_label", "title": "Meaning"}, {"field": "share_label", "title": "Share"}]}}


def _size_rows(kind, thumb):
    spec = _size_spec(thumb)
    spec["transform"] = [{"filter": f"datum.group_kind === '{kind}'"}]
    return spec


def _scatter_spec():
    return {"data": _src("dq_org_scatter"), **SIZE, "height": "container", "padding": {"left": 4, "right": 8, "top": 8, "bottom": 4},
            "layer": [
                {"mark": {"type": "rule", "opacity": 0.35, "clip": True}, "encoding": {"x": {"field": "record_count", "type": "quantitative", "scale": {"type": "log", "domain": [8, 300]}, "title": "Registrations in the season (log scale)"},
                    "y": {"field": "score_interval_low", "type": "quantitative", "scale": {"domain": [40, 100]}, "title": "Score for splitting by age and gender"}, "y2": {"field": "score_interval_high"},
                    "color": {"field": "channel_plain", "type": "nominal", "title": None, "legend": {"orient": "top", "labelLimit": 400, "labelFontSize": 13, "symbolStrokeWidth": 4}}}},
                {"mark": {"type": "point", "filled": True, "size": 60, "clip": True}, "encoding": {"x": {"field": "record_count", "type": "quantitative", "scale": {"type": "log", "domain": [8, 300]}},
                    "y": {"field": "score", "type": "quantitative", "scale": {"domain": [40, 100]}}, "color": {"field": "channel_plain", "type": "nominal", "legend": None},
                    "shape": {"field": "channel_plain", "type": "nominal", "legend": None},
                    "tooltip": [{"field": "channel_plain", "title": "How it sends data"}, {"field": "record_count", "title": "Registrations"}, {"field": "score", "title": "Score"}, {"field": "grade", "title": "Grade"}]}}]}


def render_fix_letter(rows) -> str:
    """One league's fix list as a short letter: bold action, one line of why, and the scale. Counts only; no record or person is named."""
    from html import escape as e
    if not rows:
        return "<p class='note'>No fix list for this league.</p>"
    items = []
    for r in rows:
        if r["is_no_file"]:
            action = r["plain_action"]
            scale = f"Right now {r['scale_text'].replace(' (estimated)', '')} from this league are missing from every count (estimated)."
        else:
            action = r["plain_action"]
            scale = f"Affects {r['scale_text']}."
        items.append(f"<li><b>{e(action)}</b><br><span class='note'>{e(r['why'])}</span><br><span class='fixscale'>{e(scale)}</span></li>")
    return (f"<div class='fixletter'><p class='fixto'><b>{e(rows[0]['league_label'])}</b> \u00b7 {e(rows[0]['profile_label'])}</p>"
            f"<p class='fixlead'>Here is what to fix first:</p><ol>{''.join(items)}</ol></div>")


def quality_cards():
    uses = [("COUNT", "Counting players"), ("SEGMENT", "Breaking down by age and gender"), ("GEO", "Placing players on the map"), ("RETAIN", "Tracking who comes back"), ("ACTIVATE", "Contacting families")]
    C = {}
    C["q1_grid"] = dict(
        page="quality", title="Which data can I trust, and for what?", datasets=["dq_grid", "dq_dims"],
        card=dict(id="Q1", datasets=["dq_grid", "dq_dims"], thumb=_grid_spec(True), open_slide=1,
                  slides=[dict(title="All sources and uses", key="GRID", spec=_grid_spec(False))] + [dict(title=label, key=use, spec=_dims_spec(use)) for use, label in uses]))
    C["q2_trend"] = dict(
        page="quality", title="Is quality changing?", datasets=["dq_trend_lines"],
        card=dict(id="Q2", datasets=["dq_trend_lines"], thumb=_trend_spec("ACTIVATE", True), open_slide=5,
                  slides=[dict(title=label, key=use, spec=_trend_spec(use, False)) for use, label in uses]))
    C["q4_size"] = dict(
        page="quality", title="Is it small leagues, or everyone?", datasets=["dq_org_grades", "dq_org_scatter"],
        card=dict(id="Q4", datasets=["dq_org_grades", "dq_org_scatter"], thumb=_size_rows("League size", True), open_slide=1,
                  slides=[dict(title="By league size", key="SIZE", spec=_size_rows("League size", False)), dict(title="By how the league sends data", key="CHANNEL", spec=_size_rows("How the league sends data", False)),
                          dict(title="Every league (for analysts)", key="SCATTER", spec=_scatter_spec())]))
    C["q5_fix"] = dict(
        page="quality", title="What do we ask a league to do?", datasets=["dq_fix_examples"],
        card=dict(id="Q5", datasets=["dq_fix_examples"], thumb=None, thumb_html=lambda d: render_fix_letter([r for r in d["dq_fix_examples"]["rows"] if r["example_no"] == 1]), open_slide=1,
                  slides=[dict(title=f"Example {n}", key=f"EX{n}", html=(lambda n: lambda d: render_fix_letter([r for r in d["dq_fix_examples"]["rows"] if r["example_no"] == n]))(n)) for n in (1, 2, 3)]))
    return C


def render_tiles(rows, use, compact=False) -> str:
    """One use's tile map as HTML: tiles grouped by state, west to east. Grade letter, market name, players, leagues reporting. Empty markets are outlined tiles."""
    from html import escape as e
    mine = sorted((r for r in rows if r["purpose"] == use), key=lambda r: (r["state_order"], r["market_no"]))
    states: dict = {}
    for r in mine:
        states.setdefault(r["state_name"], []).append(r)
    out = []
    for name, tiles in states.items():
        cells = []
        for t in tiles:
            if t["status"] == "No data yet":
                cls, letter, label = "g-none", "", "No data yet"
            elif t["status"] == "Hidden":
                cls, letter, label = "g-hidden", "", t["players_text"]
            else:
                cls, letter, label = f"g-{t['grade']}", t["grade"], t["players_text"]
            detail = f"<span class='mdetail'>{e(label)}</span>" + (f"<span class='mdetail'>{e(t['leagues_text'])}</span>" if t["leagues_text"] else "")
            cells.append(f"<div class='mtile {cls}' title='{e(t['plain_name'])}: {e(label)}'><span class='mletter'>{e(letter) or '&nbsp;'}</span><span class='mname'>{e(t['plain_name'])}</span>{detail}</div>")
        out.append(f"<div class='vstate'><h4>{e(name)}</h4><div class='vstate-row'>{''.join(cells)}</div></div>")
    return f"<div class='vtiles{' vtiles-compact' if compact else ''}' data-use='{use}'>{''.join(out)}</div>"


def render_pair(pair, grades) -> str:
    """The same market through two lenses, side by side: what the club sees and what the privacy lead sees. Counts only; the club receives no name, birth date or contact detail."""
    from html import escape as e
    rng = f"<p class='note'>That is {e(pair['range_text'])}.</p>" if pair["range_text"] else ""
    lines = "".join(f"<div class='gradeline'><span class='gl g-{g['grade']}'>{e(g['grade'])}</span><span>{e(g['purpose_label'])}: {e(g['grade_label'].lower())}</span></div>" for g in grades)
    club = (f"<div class='lenspanel'><h4>Club lens · {e(pair['plain_name'])}</h4><p><b>{e(pair['players_text'])}</b> played here.</p>{rng}"
            f"<p>{e(pair['leagues_text'])}.</p>{lines}<p>{e(pair['reach_text'][0].upper() + pair['reach_text'][1:])}.</p></div>")
    priv = (f"<div class='lenspanel'><h4>Privacy lens · {e(pair['plain_name'])}</h4><p>{e(pair['receives_text'])}</p>"
            f"<p><b>What never leaves the league:</b> names, birth dates and contact details.</p><p>{e(pair['consent_text'][0].upper() + pair['consent_text'][1:])}.</p>"
            f"<p class='note'>Families who said no, or were never asked, are not contacted. That is the design working.</p></div>")
    return f"<div class='lenspair'>{club}{priv}</div>"


def _growth_panel(name, small):
    safe = name.replace("'", "\\'")
    xe = {"field": "participation_year", "type": "ordinal", "title": None, "axis": {"labelAngle": 0, "labelFontSize": 9 if small else 12, "labelOverlap": True}}
    ye = {"field": "growth_index", "type": "quantitative", "title": None, "scale": {"zero": False}, "axis": {"tickCount": 3 if small else 5, "format": "d", "labelFontSize": 9 if small else 12}}
    ylo = {"field": "index_low", "type": "quantitative", "scale": {"zero": False}}
    return {"data": _src("market_growth"), "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"}, "padding": 2,
            "transform": [{"filter": f"datum.plain_name === '{safe}'"}],
            "layer": [
                {"mark": {"type": "area", "opacity": 0.25, "clip": True, "color": "#3D7CC9"}, "encoding": {"x": xe, "y": ylo, "y2": {"field": "index_high"}}},
                {"mark": {"type": "line", "strokeDash": [4, 3], "color": "#3D7CC9", "strokeWidth": 1, "clip": True}, "encoding": {"x": xe, "y": ylo}},
                {"mark": {"type": "line", "strokeDash": [4, 3], "color": "#3D7CC9", "strokeWidth": 1, "clip": True}, "encoding": {"x": xe, "y": {"field": "index_high", "type": "quantitative", "scale": {"zero": False}}}},
                {"mark": {"type": "line", "point": True, "color": "#14263B", "clip": True, "strokeWidth": 2}, "encoding": {"x": xe, "y": ye,
                    "tooltip": [{"field": "plain_name", "title": "Market"}, {"field": "participation_year", "title": "Season"}, {"field": "growth_index", "title": "Index (first year = 100)"},
                                {"field": "index_low", "title": "Range from"}, {"field": "index_high", "title": "to"}]}}]}


def _funnel_spec(slide_no, thumb):
    y = {"field": "step_name", "type": "nominal", "title": None, "sort": {"field": "display_no", "op": "min"}, "axis": {"labelLimit": 360, "labelFontSize": 11 if thumb else 14}}
    return {"data": _src("market_funnel"), "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"}, "padding": {"left": 4, "right": 12, "top": 4, "bottom": 4},
            "transform": [{"filter": f"datum.slide_no === {slide_no}"}],
            "layer": [
                {"mark": {"type": "bar", "clip": True, "height": {"band": 0.7}, "stroke": "#ffffff", "strokeWidth": 1}, "encoding": {"y": y,
                    "x": {"field": "x0", "type": "quantitative", "title": None if thumb else "Players or families", "axis": {"format": ",d", "tickCount": 4 if thumb else 8}}, "x2": {"field": "x1"},
                    "color": {"field": "part", "type": "nominal", "title": None, "scale": {"domain": ["Still reachable", "Fixable data problem", "Family's choice or never asked"], "range": ["#3D7CC9", "#D9622B", "#7D4E8E"]},
                              "legend": {"orient": "top", "labelLimit": 400, "labelFontSize": 11 if thumb else 13, "symbolType": "square"}},
                    "tooltip": [{"field": "step_name", "title": "Step"}, {"field": "part", "title": "Part"}, {"field": "amount_label", "title": "Amount"}]}},
                {"mark": {"type": "text", "color": "#ffffff", "fontSize": 11 if thumb else 13, "fontWeight": "bold", "clip": True}, "encoding": {"y": y, "x": {"field": "x_mid", "type": "quantitative"}, "text": {"field": "bar_label", "type": "nominal"}}}]}


def _orgs_spec(slide_no, thumb):
    y = {"field": "plain_name", "type": "nominal", "title": None, "sort": {"field": "dark_rank", "op": "min"}, "axis": {"labelLimit": 300, "labelFontSize": 11 if thumb else 13}}
    return {"data": _src("market_orgs"), "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"}, "padding": {"left": 4, "right": 4 if thumb else 190, "top": 4, "bottom": 4},
            "transform": [{"filter": f"datum.slide_no === {slide_no}" + (" && datum.dark_rank <= 6" if thumb else "")}],
            "layer": [
                {"mark": {"type": "bar", "clip": True, "height": {"band": 0.7}, "stroke": "#ffffff", "strokeWidth": 1}, "encoding": {"y": y,
                    "x": {"field": "x0", "type": "quantitative", "title": None if thumb else "Share of known leagues (%)", "scale": {"domain": [0, 100]}, "axis": {"format": "d", "tickCount": 5}}, "x2": {"field": "x1"},
                    "color": {"field": "part", "type": "nominal", "title": None, "scale": {"domain": ["Sent data", "Sent no data"], "range": ["#2F6B4F", "#B8A06A"]}, "legend": {"orient": "top", "labelFontSize": 11 if thumb else 13}},
                    "tooltip": [{"field": "plain_name", "title": "Market"}, {"field": "part", "title": "Part"}, {"field": "leagues_text", "title": "Leagues"}]}}]
            + ([] if thumb else [{"transform": [{"filter": "datum.part_order === 1"}],
                                  "mark": {"type": "text", "align": "left", "dx": 6, "fontSize": 12, "clip": False, "color": "#4A5866"},
                                  "encoding": {"y": y, "x": {"field": "label_x", "type": "quantitative"}, "text": {"field": "leagues_text", "type": "nominal"}}}])}


def market_cards():
    uses = [("COUNT", "Counting players"), ("SEGMENT", "Breaking down by age and gender"), ("GEO", "Placing players on the map"), ("RETAIN", "Tracking who comes back"), ("ACTIVATE", "Contacting families")]

    def pre(d):
        btns = "".join(f"<button type='button' data-seg='{u}' aria-pressed='{'true' if u == 'COUNT' else 'false'}'>{label}</button>" for u, label in uses)
        return f"<div class='vseg' role='group' aria-label='Choose a use'>{btns}</div>"

    def thumb_tiles(d):
        rows = d["market_tiles"]["rows"]
        return "<span class='vtiles-host' data-active='COUNT'>" + "".join(render_tiles(rows, u, True) for u, _ in uses) + "</span>"

    def growth_slides(d):
        names: dict = {}
        for r in d["market_growth"]["rows"]:
            names.setdefault(r["slide_no"], {})[r["size_rank"]] = r["plain_name"]
        return [dict(title=f"Markets {min(v)} to {max(v)} by size", key="GROWTH", multi=[dict(title=v[k], spec=_growth_panel(v[k], False)) for k in sorted(v)]) for _, v in sorted(names.items())]

    def growth_thumb(d):
        first = {}
        for r in d["market_growth"]["rows"]:
            if r["slide_no"] == 1:
                first[r["size_rank"]] = r["plain_name"]
        return [dict(title=first[k], spec=_growth_panel(first[k], True)) for k in sorted(first)]

    def funnel_slides(d):
        seen = {}
        for r in d["market_funnel"]["rows"]:
            seen[r["slide_no"]] = r["slide_title"]
        return [dict(title=t, key="ALL" if n == 0 else "MARKET", spec=_funnel_spec(n, False)) for n, t in sorted(seen.items())]

    def orgs_slides(d):
        nos = sorted({r["slide_no"] for r in d["market_orgs"]["rows"]})
        return [dict(title=f"Markets, part {i}" if len(nos) > 1 else "All markets", key="ORGS", spec=_orgs_spec(n, False)) for i, n in enumerate(nos, 1)]

    def pair_html(d, n):
        pair = next(r for r in d["market_pairs"]["rows"] if r["slide_no"] == n)
        return render_pair(pair, [g for g in d["market_pair_grades"]["rows"] if g["slide_no"] == n])

    def pair_slides(d):
        return [dict(title=r["plain_name"], key="PAIR", html=(lambda n: lambda dd: pair_html(dd, n))(r["slide_no"])) for r in d["market_pairs"]["rows"]]

    C = {}
    C["m1_tiles"] = dict(page="markets", title="How's my market?", datasets=["market_tiles"],
        card=dict(id="M1", datasets=["market_tiles"], thumb_html=thumb_tiles, pre_html=pre, open_slide=1,
                  slides=lambda d: [dict(title=label, key=u, html=(lambda u: lambda dd: render_tiles(dd["market_tiles"]["rows"], u))(u)) for u, label in uses]))
    C["m2_growth"] = dict(page="markets", title="Is growth real, or just better reporting?", datasets=["market_growth"],
        card=dict(id="M2", datasets=["market_growth"], thumb_multi=growth_thumb, open_slide=1, slides=growth_slides))
    C["m3_funnel"] = dict(page="markets", title="Why can't I reach more families?", datasets=["market_funnel"],
        card=dict(id="M3", datasets=["market_funnel"], thumb=_funnel_spec(0, True), open_slide=1, slides=funnel_slides))
    C["m4_dark"] = dict(page="markets", title="How much of my market can't we see?", datasets=["market_orgs", "market_no_leagues"],
        card=dict(id="M4", datasets=["market_orgs", "market_no_leagues"], thumb=_orgs_spec(1, True), open_slide=1, slides=orgs_slides,
                  note_html=lambda d: ("<p class='vnote'><b>No leagues known yet:</b> " + ", ".join(__import__("html").escape(r["plain_name"]) for r in d["market_no_leagues"]["rows"]) + ".</p>") if d["market_no_leagues"]["rows"] else ""))
    C["m5_pair"] = dict(page="markets", title="The same market, two lenses", datasets=["market_pairs", "market_pair_grades"],
        card=dict(id="M5", datasets=["market_pairs", "market_pair_grades"], thumb_html=lambda d: pair_html(d, 1), open_slide=1, slides=pair_slides))
    return C


def _latest(d, ds, key="participation_year"):
    return max(r[key] for r in d[ds]["rows"])


def _unc_spec(year, thumb):
    y = {"field": "component_label", "type": "nominal", "title": None, "sort": {"field": "component_order", "op": "min"}, "axis": {"labelLimit": 300, "labelFontSize": 12 if thumb else 14}}
    return {"data": _src("unc_decomp"), "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"}, "padding": {"left": 4, "right": 12, "top": 4, "bottom": 4},
            "transform": [{"filter": f"datum.participation_year === {year}"}],
            "layer": [
                {"mark": {"type": "rule", "strokeWidth": 10 if thumb else 14, "opacity": 0.6, "clip": True}, "encoding": {"y": y,
                    "x": {"field": "interval_low", "type": "quantitative", "scale": {"zero": False}, "title": None if thumb else "Players counted", "axis": {"format": ",d", "tickCount": 4 if thumb else 8}}, "x2": {"field": "interval_high"},
                    "color": {"field": "component_label", "type": "nominal", "legend": None, "scale": {"range": ["#3D7CC9", "#D9622B", "#B8A06A"]}},
                    "tooltip": [{"field": "component_label", "title": "Source of doubt"}, {"field": "reported_point", "title": "Counted"}, {"field": "interval_low", "title": "Low"}, {"field": "interval_high", "title": "High"}]}},
                {"mark": {"type": "tick", "color": "#000000", "thickness": 3, "size": 26 if thumb else 34, "clip": True}, "encoding": {"y": y, "x": {"field": "reported_point", "type": "quantitative"}}}]}


def _miss_spec(year, thumb):
    y = {"field": "division", "type": "nominal", "title": None, "axis": {"labelFontSize": 12 if thumb else 14}}
    return {"data": _src("miss_dumbbell"), "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"}, "padding": {"left": 4, "right": 12, "top": 4, "bottom": 4},
            "transform": [{"filter": f"datum.participation_year === {year}"}],
            "layer": [
                {"mark": {"type": "rule", "strokeWidth": 6, "opacity": 0.5, "clip": True, "color": "#8A96A3"}, "encoding": {"y": y,
                    "x": {"field": "bound_low_pct", "type": "quantitative", "scale": {"zero": False}, "title": None if thumb else "Girls' share of players (%)", "axis": {"format": "d", "tickCount": 5}}, "x2": {"field": "bound_high_pct"}}},
                {"mark": {"type": "point", "filled": True, "color": "#D9622B", "size": 80 if thumb else 120, "clip": True}, "encoding": {"y": y, "x": {"field": "girls_pct", "type": "quantitative"},
                    "tooltip": [{"field": "division", "title": "Age group"}, {"field": "girls_pct", "title": "Girls' share, known only (%)"}, {"field": "bound_low_pct", "title": "Lowest it could be"},
                                {"field": "bound_high_pct", "title": "Highest it could be"}, {"field": "unknown", "title": "Gender not recorded"}, {"field": "total", "title": "Players"}]}}]}


def _truth_spec(year, thumb):
    y = {"field": "component", "type": "nominal", "title": None, "axis": {"labelLimit": 300, "labelFontSize": 12 if thumb else 14}}
    return {"data": _src("unc_truth"), "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"}, "padding": {"left": 4, "right": 12, "top": 4, "bottom": 4},
            "transform": [{"filter": f"datum.participation_year === {year}"}],
            "layer": [
                {"mark": {"type": "rule", "strokeWidth": 10 if thumb else 14, "opacity": 0.6, "clip": True}, "encoding": {"y": y,
                    "x": {"field": "low", "type": "quantitative", "scale": {"zero": False}, "title": None if thumb else "Players counted", "axis": {"format": ",d", "tickCount": 4 if thumb else 8}}, "x2": {"field": "high"},
                    "color": {"field": "truth_inside", "type": "nominal", "title": None, "scale": {"domain": [True, False], "range": ["#2F6B4F", "#D9622B"]},
                              "legend": {"orient": "top", "labelExpr": "datum.value ? 'True number inside the range' : 'True number outside the range'", "labelLimit": 400}}}},
                {"mark": {"type": "point", "shape": "cross", "color": "#000000", "size": 120, "strokeWidth": 2.5, "clip": True}, "encoding": {"y": y, "x": {"field": "truth", "type": "quantitative"},
                    "tooltip": [{"field": "component", "title": "Method"}, {"field": "truth", "title": "True number (synthetic answer key)"}, {"field": "low", "title": "Range from"}, {"field": "high", "title": "to"}]}}]}


def _fixdemo_spec(group, thumb):
    safe = group.replace("'", "\\'")
    y = {"field": "purpose", "type": "nominal", "sort": PURPOSES, "title": None, "axis": {"labelFontSize": 12 if thumb else 14}}
    return {"data": _src("fix_demo_scores"), "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"}, "padding": {"left": 4, "right": 12, "top": 4, "bottom": 4},
            "transform": [{"filter": f"datum.org_group === '{safe}'"}],
            "layer": [
                {"mark": {"type": "rule", "strokeWidth": 3, "color": "#8A96A3", "clip": True}, "encoding": {"y": y, "x": {"field": "score_before", "type": "quantitative", "scale": {"domain": [50, 100]}, "title": None if thumb else "Quality score"}, "x2": {"field": "score_after"}}},
                {"mark": {"type": "point", "filled": True, "color": "#8A96A3", "size": 90, "clip": True}, "encoding": {"y": y, "x": {"field": "score_before", "type": "quantitative"}, "tooltip": [{"field": "purpose", "title": "Use"}, {"field": "score_before", "title": "Before"}, {"field": "score_after", "title": "After"}]}},
                {"mark": {"type": "point", "filled": True, "color": "#2F6B4F", "size": 110, "shape": "diamond", "clip": True}, "encoding": {"y": y, "x": {"field": "score_after", "type": "quantitative"}}}]}


def sure_cards():
    def slides_for(ds, fn):
        return lambda d: [dict(title=str(yr), key="YEAR", spec=fn(yr, False)) for yr in sorted({r["participation_year"] for r in d[ds]["rows"]}, reverse=True)]

    C = {}
    C["u1_decomp"] = dict(page="sure", title="Why is there a range, not one number?", datasets=["unc_decomp"],
        card=dict(id="U1", datasets=["unc_decomp"], thumb=lambda d: _unc_spec(_latest(d, "unc_decomp"), True), open_slide=1, slides=slides_for("unc_decomp", _unc_spec)))
    C["u2_missing"] = dict(page="sure", title="Is the girls' trend real?", datasets=["miss_dumbbell"],
        card=dict(id="U2", datasets=["miss_dumbbell"], thumb=lambda d: _miss_spec(_latest(d, "miss_dumbbell"), True), open_slide=1, slides=slides_for("miss_dumbbell", _miss_spec)))
    C["u3_overlay"] = dict(page="sure", title="Do the methods work?", datasets=["unc_truth"], evaluation=True,
        card=dict(id="U3", datasets=["unc_truth"], thumb=lambda d: _truth_spec(_latest(d, "unc_truth"), True), open_slide=1, slides=slides_for("unc_truth", _truth_spec)))
    groups = lambda d: sorted({r["org_group"] for r in d["fix_demo_scores"]["rows"]}, reverse=True)
    C["u4_fixdemo"] = dict(page="sure", title="What is the payoff of fixing problems early?", datasets=["fix_demo_scores", "fix_demo_nuance"], evaluation=True,
        card=dict(id="U4", datasets=["fix_demo_scores", "fix_demo_nuance"], thumb=lambda d: _fixdemo_spec(groups(d)[0], True), open_slide=1,
                  slides=lambda d: [dict(title=g.replace("Organizations", "Leagues").replace("organizations", "leagues"), key="GROUP", spec=_fixdemo_spec(g, False)) for g in groups(d)]))
    return C


def _prov_spec(thumb):
    y = {"field": "form", "type": "nominal", "title": None, "axis": {"labelLimit": 420, "labelFontSize": 11 if thumb else 13}}
    return {"data": _src("consent_prov"), "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"}, "padding": {"left": 4, "right": 12, "top": 4, "bottom": 4},
            "mark": {"type": "bar", "clip": True, "height": {"band": 0.7}, "stroke": "#ffffff", "strokeWidth": 1},
            "encoding": {"y": y, "x": {"field": "x0", "type": "quantitative", "title": None if thumb else "Consent records, latest season", "axis": {"format": ",d", "tickCount": 4 if thumb else 8}}, "x2": {"field": "x1"},
                         "color": {"field": "provenance_label", "type": "nominal", "title": None, "scale": {"domain": ["Fully recorded", "Partly recorded", "Not recorded"], "range": ["#2F6B4F", "#B8A06A", "#8A96A3"]},
                                   "legend": {"orient": "top", "labelFontSize": 11 if thumb else 13, "columns": 1 if thumb else 3}},
                         "tooltip": [{"field": "form", "title": "Source and form"}, {"field": "provenance_label", "title": "Recorded"}, {"field": "consent_events", "title": "Consent records"}]}}


def _matrix_spec(thumb):
    x = {"field": "purpose_label", "type": "nominal", "title": None, "axis": {"orient": "top", "labelAngle": 0, "labelLimit": 220, "labelFontSize": 11 if thumb else 13}}
    y = {"field": "form", "type": "nominal", "title": None, "axis": {"labelLimit": 360, "labelFontSize": 11 if thumb else 13}}
    return {"data": _src("purpose_matrix"), "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"}, "padding": {"left": 4, "right": 12, "top": 4, "bottom": 4},
            "layer": [
                {"mark": {"type": "rect", "stroke": "#ffffff", "strokeWidth": 2, "clip": True}, "encoding": {"x": x, "y": y,
                    "color": {"field": "coverage", "type": "nominal", "scale": {"domain": ["Named on the form", "Not named"], "range": ["#92c5de", "#f4a582"]}, "title": None, "legend": {"orient": "bottom"}}}},
                {"mark": {"type": "text", "fontSize": 13 if thumb else 16, "fontWeight": "bold"}, "encoding": {"x": x, "y": y, "text": {"field": "mark", "type": "nominal"}}}]}


def _retention_spec(thumb):
    return {"data": _src("retention_del"), "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"}, "padding": {"left": 4, "right": 12, "top": 4, "bottom": 4},
            "mark": {"type": "bar", "clip": True},
            "encoding": {"y": {"field": "metric_label", "type": "nominal", "title": None, "axis": {"labelLimit": 380, "labelFontSize": 11 if thumb else 13}},
                         "x": {"field": "change", "type": "quantitative", "axis": {"format": "%"}, "title": None if thumb else "Change in the figure after deletion"},
                         "yOffset": {"field": "scenario", "type": "nominal"},
                         "color": {"field": "scenario", "type": "nominal", "title": None, "scale": {"range": ["#2F6B4F", "#D9622B"]}, "legend": {"orient": "top", "labelLimit": 400}},
                         "tooltip": [{"field": "metric_label", "title": "Figure"}, {"field": "scenario", "title": "Scenario"}, {"field": "change", "title": "Change", "format": ".1%"}]}}


def _kanon_spec(thumb):
    xe = {"field": "participation_year", "type": "ordinal", "title": None, "axis": {"labelAngle": 0}}
    return {"data": _src("analyst_k"), "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"}, "padding": {"left": 4, "right": 12, "top": 8, "bottom": 4},
            "layer": [
                {"mark": {"type": "line", "point": True, "color": "#7D4E8E", "clip": True, "strokeWidth": 2}, "encoding": {"x": xe, "y": {"field": "pct_unique", "type": "quantitative", "scale": {"domain": [0, 100]},
                    "title": None if thumb else "Participant-years that are unique (%)", "axis": {"format": "d"}},
                    "tooltip": [{"field": "participation_year", "title": "Season"}, {"field": "pct_unique", "title": "Unique (%)"}, {"field": "smallest_class", "title": "Smallest group"}]}}]}


def _frontier_spec(thumb):
    spec = {"data": _src("frontier"), "width": "container", "height": "container", "autosize": {"type": "fit", "contains": "padding"}, "padding": {"left": 4, "right": 12, "top": 12, "bottom": 4},
            "layer": [
                {"mark": {"type": "line", "color": "#8A96A3", "strokeDash": [4, 3], "clip": True}, "encoding": {"x": {"field": "pct_unique", "type": "quantitative", "title": None if thumb else "Participant-years that are unique (%): lower is safer", "scale": {"zero": False}},
                    "y": {"field": "f1", "type": "quantitative", "scale": {"domain": [0.99, 1.0]}, "title": None if thumb else "Matching accuracy (F1)", "axis": {"format": ".1%", "tickCount": 5}}, "order": {"field": "variant_id"}}},
                {"mark": {"type": "point", "filled": True, "size": 110 if thumb else 160, "clip": True}, "encoding": {"x": {"field": "pct_unique", "type": "quantitative"}, "y": {"field": "f1", "type": "quantitative"},
                    "color": {"field": "short_label", "type": "nominal", "title": None, "legend": {"orient": "top", "labelLimit": 400, "columns": 2 if thumb else 5, "labelFontSize": 11 if thumb else 13}},
                    "tooltip": [{"field": "variant_label", "title": "Fields kept"}, {"field": "pct_unique", "title": "Unique (%)"}, {"field": "f1", "title": "Matching accuracy", "format": ".1%"}, {"field": "sibling_or_twin_false_merges", "title": "Sibling or twin mix-ups"}]}},
                {"mark": {"type": "point", "filled": False, "size": 420, "strokeWidth": 3, "clip": True}, "encoding": {"x": {"field": "pct_unique", "type": "quantitative"}, "y": {"field": "f1", "type": "quantitative"},
                    "stroke": {"field": "in_standard", "type": "nominal", "scale": {"domain": [True, False], "range": ["#000000", "rgba(0,0,0,0)"]}, "legend": None}}},
                {"mark": {"type": "text", "dy": -16, "fontSize": 11 if thumb else 13, "clip": False}, "encoding": {"x": {"field": "pct_unique", "type": "quantitative"}, "y": {"field": "f1", "type": "quantitative"}, "text": {"field": "short_label", "type": "nominal"}}}]}
    return spec


def privacy_cards():
    C = {}
    one = lambda fn: (lambda d: [dict(title="Chart", key="ONE", spec=fn(False))])
    C["p3_frontier"] = dict(page="privacy", title="What does each field buy us, and what does it cost?", datasets=["frontier"], evaluation=True,
        card=dict(id="P3", datasets=["frontier"], thumb=_frontier_spec(True), open_slide=1, slides=one(_frontier_spec)))
    C["p1_provenance"] = dict(page="privacy", title="Do we know what families agreed to?", datasets=["consent_prov"],
        card=dict(id="P1", datasets=["consent_prov"], thumb=_prov_spec(True), open_slide=1, slides=one(_prov_spec)))
    C["p2_matrix"] = dict(page="privacy", title="Which purposes does each consent form cover?", datasets=["purpose_matrix"],
        card=dict(id="P2", datasets=["purpose_matrix"], thumb=_matrix_spec(True), open_slide=1, slides=one(_matrix_spec)))
    C["p4_retention"] = dict(page="privacy", title="Can we delete and still measure who comes back?", datasets=["retention_del"],
        card=dict(id="P4", datasets=["retention_del"], thumb=_retention_spec(True), open_slide=1, slides=one(_retention_spec)))
    C["p5_kanon"] = dict(page="privacy", title="How identifying is the analyst share?", datasets=["analyst_k"],
        card=dict(id="P5", datasets=["analyst_k"], thumb=_kanon_spec(True), open_slide=1, slides=one(_kanon_spec)))
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
