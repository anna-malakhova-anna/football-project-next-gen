"""Phase 5 datasets of the results site (spec section 12): what each may read, and every dataset (SQL) for Data Quality, How Sure Are We,
Club Markets and Privacy by Design.

Split out of scripts/site_phase5.py without changing a line. The same rules apply as everywhere on the site (see scripts/site_data.py):
a dataset reads only a share table, an approved aggregate, a whitelisted evaluation summary or governance metadata. All data is SYNTHETIC.
"""
from __future__ import annotations

SHARE_PREFIXES = ("share_exec.", "share_club.", "share_privacy.")
APPROVED = {
    "quality.dq_scorecard_source", "quality.dq_scorecard_org", "quality.dq_trend", "quality.mart_dq_impact", "quality.dq_fix_ranking",
    "quality.mart_uncertainty_decomposition", "quality.mart_missingness_bias",
}
EVAL = {"evaluation.eval_chart_insights", "evaluation.eval_uncertainty_decomposition", "evaluation.eval_minimization_tradeoff", "demo_fix_list.scores", "demo_fix_list.nuance"}
GOVERNANCE = {"reference.privacy_params", "reference.dq_purposes", "reference.club_market_map", "reference.funnel_step_display", "reference.p5_params", "reference.source_display", "reference.dq_dimensions", "reference.dq_grade_bands", "reference.channel_display", "reference.dq_rule_registry", "reference.dq_purposes"}

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
               s.purpose, rtrim(regexp_replace(p.plain_label, '(.{{1,9}})( |$)', '\\1' || chr(10), 'g'), chr(10)) as purpose_wrapped, p.plain_label as purpose_label, rtrim(regexp_replace(p.plain_label, '(.{{1,22}})( |$)', '\\1' || chr(10), 'g'), chr(10)) as purpose_wrapped_wide,
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
        order by o.record_count, o.org_id""", ["quality.dq_scorecard_org", "quality.dq_scorecard_source", "reference.channel_display"], "approved_aggregate", "League score against league size, latest season"),
    _D("dq_fix_examples", f"""
        with f as (
            select f.org_id, f.rule_id, f.rank_in_scope, f.impact_estimate, f.impact_unit, f.impact_basis, f.purposes_breached
            from quality.dq_fix_ranking f where f.season_year = {LATEST_Q} and not f.is_systemic and f.rank_in_scope <= 3),
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
        order by pk.example_no, f.rank_in_scope""", ["quality.dq_fix_ranking", "quality.dq_scorecard_org", "quality.dq_scorecard_source", "reference.dq_rule_registry", "reference.dq_purposes", "reference.privacy_params"], "approved_aggregate",
       "Example fix lists for three made-up leagues, one per quality profile"),
    _D("unc_decomp", """
        select participation_year, component,
               case component when 'IDENTITY' then 'Matching people' when 'DQ_EXCLUSIONS' then 'Records that fail the rules' else 'Leagues that sent no file' end as component_label,
               case component when 'IDENTITY' then 1 when 'DQ_EXCLUSIONS' then 2 else 3 end as component_order,
               cast(round(reported_point, -1) as bigint) as reported_point, cast(round(interval_low, -1) as bigint) as interval_low, cast(round(interval_high, -1) as bigint) as interval_high
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
        order by p.purpose_order, state_order, market_no, mk.club_market_id""", ["share_club.share_club__market_year", "reference.club_market_map", "reference.dq_purposes", "reference.privacy_params"], "share_club",
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
    _D("glossary_checks", """
        select 'Use' as kind, plain_label as term, plain_question as meaning, purpose as technical from reference.dq_purposes
        union all select 'Quality check', plain_label, 'One of the checks behind a grade.', dimension from reference.dq_dimensions where dimension <> 'PURPOSE_SCORE'
        union all select 'Grade', plain_label || ' (' || grade || ')', description, 'minimum score ' || cast(min_score as varchar) from reference.dq_grade_bands
        order by 1, 2""", ["reference.dq_purposes", "reference.dq_dimensions", "reference.dq_grade_bands"], "governance", "Plain names for uses, quality checks and grades"),
    _D("glossary_rules", "select plain_label as problem, plain_action as what_to_do, rule_id as technical from reference.dq_rule_registry order by plain_label",
       ["reference.dq_rule_registry"], "governance", "Plain names for every problem we check"),
    _D("chart_insights_eval", "select chart_id, lens, field, value_display, value_raw, suppressed from evaluation.eval_chart_insights order by 1, 3", ["evaluation.eval_chart_insights"], "evaluation",
       "Numbers used inside headline sentences (evaluation cards)"),
    _D("analyst_k", "select participation_year, participant_years, equivalence_classes, smallest_class, average_class_size, pct_unique, pct_rows_below_k_warn, pct_rows_below_k_min "
       "from share_privacy.share_privacy__analyst_k_anonymity order by 1", ["share_privacy.share_privacy__analyst_k_anonymity"], "share_privacy", "How identifying the analyst share is, per year"),
    _D("policy_results", "select check_name, violations from share_privacy.share_privacy__policy_checks order by 1", ["share_privacy.share_privacy__policy_checks"], "share_privacy", "Share-policy check results"),
]
