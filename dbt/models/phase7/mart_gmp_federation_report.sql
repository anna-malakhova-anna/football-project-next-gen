-- The federation report card (Phase 7, spec section 7): for each federation that sends returns (INTL_FED, one per country), in the latest season,
-- its counting grade and how it moved since the previous season, how many of its clubs filed, how many more would have to file for the market to
-- read MEASURED, and its top three fixes. Fixes come from DP1's dq_fix_list (each club's ranked fix list, records affected, no identity), summed over
-- the federation's clubs and ranked so that a fix that moves the counting grade (COUNT purpose, the number the executive's market status rests on)
-- comes first, then by records affected. DP4's impact ranking is NOT used: its impact is measured on linked households, and nothing household-linked
-- may reach a partner (ADR-009; check_share_policy LINKAGE_LEAK).
--   clubs_to_file_for_measured  set only when the grade is below the MEASURED band, timeliness is what limits it, and every other counting dimension
--                               already clears the band: then ceil(band / 100 x known clubs) - clubs that filed. Otherwise NULL (more filings alone
--                               would not be enough, or nothing is needed).
with latest as (select last_observed_year as y1, last_observed_year - 1 as y0 from {{ ref('observation_window') }}),

bar as (select min_score from {{ ref('dq_grade_bands') }} where grade = (select value from {{ ref('p7_params') }} where param = 'measured_min_grade')),

count_score as (

    select country_code, season_year, score, grade, limiting_dimension, known_orgs, reporting_orgs
    from {{ ref('dq_scorecard_country') }}
    where source_system = 'INTL_FED' and purpose = 'COUNT' and dimension = 'PURPOSE_SCORE'

),

other_dims as (

    select country_code, min(score) as lowest_other_dimension
    from {{ ref('dq_scorecard_country') }}
    where source_system = 'INTL_FED' and purpose = 'COUNT' and dimension not in ('PURPOSE_SCORE', 'TIMELINESS') and season_year = (select y1 from latest)
    group by 1

),

head as (

    select n.country_code, m.country_name, n.season_year, n.score as counting_score, n.grade as counting_grade, p.grade as previous_counting_grade,
           round(n.score - p.score, 2) as counting_score_change, n.limiting_dimension, n.known_orgs as clubs_known, n.reporting_orgs as clubs_filed,
           case when n.score < (select min_score from bar) and n.limiting_dimension = 'TIMELINESS' and o.lowest_other_dimension >= (select min_score from bar)
                then greatest(0, ceil((select min_score from bar) / 100.0 * n.known_orgs)::integer - n.reporting_orgs) end as clubs_to_file_for_measured,
           s.status
    from count_score n
    join {{ ref('gmp_markets') }} m using (country_code)
    join {{ ref('mart_gmp_market_status') }} s using (country_code)
    left join count_score p on p.country_code = n.country_code and p.season_year = (select y0 from latest)
    left join other_dims o on o.country_code = n.country_code
    where n.season_year = (select y1 from latest)

),

fixes as (

    select split_part(f.org_id, '|', 1) as country_code, f.rule_id, any_value(f.fix_guidance) as fix_guidance, any_value(f.dimension) as dimension,
           bool_or(list_contains(f.purposes_breached, 'COUNT')) as moves_counting_grade,
           count(distinct f.org_id) as clubs_affected, sum(f.records_affected) as records_affected
    from {{ ref('dq_fix_list') }} f
    where f.source_system = 'INTL_FED' and f.season_year = (select y1 from latest)
    group by 1, 2

),

ranked as (

    select *, row_number() over (partition by country_code order by moves_counting_grade desc, records_affected desc, rule_id) as fix_rank
    from fixes

)

select h.*, r.fix_rank, r.rule_id, r.fix_guidance, r.dimension as fix_dimension, r.moves_counting_grade, r.clubs_affected, r.records_affected
from head h
left join ranked r on r.country_code = h.country_code and r.fix_rank <= 3
order by h.country_code, r.fix_rank
