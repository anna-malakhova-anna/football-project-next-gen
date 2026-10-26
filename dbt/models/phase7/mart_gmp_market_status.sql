-- depends_on: {{ ref('p7_params') }}
-- Market status for the 22 program markets in the latest observed season (ADR-025 section 1), one row per market:
--   MEASURED    a participation source filed in the latest season and the market's counting grade is at or above measured_min_grade
--   PARTIAL     a participation source exists, but the grade is below that band or no organization filed in the latest season
--   PROXY_ONLY  no participation source, and the latest club proxy return shows a signal (events, a game, or a national federation)
--   DARK        no participation source and no proxy signal
-- The counting grade is dq_scorecard_country (DP4's aggregate port), COUNT purpose. Clubs with rights are counted here from gmp_club_rights.
with latest as (select last_observed_year as season_year from {{ ref('observation_window') }}),

markets as (

    select m.country_code, m.country_name, m.region, m.legal_regime_id, r.output_port, m.status_on_page,
           (select count(*) from {{ ref('gmp_club_rights') }} c where c.country_code = m.country_code) as clubs_with_rights
    from {{ ref('gmp_markets') }} m join {{ ref('legal_regime') }} r using (legal_regime_id)

),

grade as (

    select s.country_code, s.source_system, s.score as counting_score, s.grade as counting_grade, s.limiting_dimension, s.known_orgs, s.reporting_orgs
    from {{ ref('dq_scorecard_country') }} s join latest l using (season_year)
    where s.purpose = 'COUNT' and s.dimension = 'PURPOSE_SCORE'

),

sourced as (select distinct country_code, source_system from {{ ref('dq_scorecard_country') }}),

proxy as (

    select p.country_code, bool_or(p.has_signal) as proxy_signal
    from {{ ref('stg_gmp_proxy') }} p join latest l using (season_year)
    where not p.is_superseded group by 1

),

bar as (select min_score from {{ ref('dq_grade_bands') }} where grade = {{ p7_param('measured_min_grade', quote=true) }})

select
    m.*,
    (select season_year from latest)                                         as season_year,
    s.source_system                                                         as participation_source,
    g.counting_score, g.counting_grade, g.limiting_dimension, g.known_orgs, g.reporting_orgs,
    coalesce(p.proxy_signal, false)                                         as proxy_signal,
    case
        when s.source_system is not null and coalesce(g.reporting_orgs, 0) > 0
             and (select min_score from {{ ref('dq_grade_bands') }} b where b.grade = g.counting_grade) >= (select min_score from bar) then 'MEASURED'
        when s.source_system is not null then 'PARTIAL'
        when p.proxy_signal then 'PROXY_ONLY'
        else 'DARK'
    end                                                                     as status,
    case
        when s.source_system is null and p.proxy_signal then 'no participation source; club proxy return shows activity'
        when s.source_system is null then 'no participation source and no proxy signal'
        when coalesce(g.reporting_orgs, 0) = 0 then 'no organization filed in the latest season'
        when (select min_score from {{ ref('dq_grade_bands') }} b where b.grade = g.counting_grade) < (select min_score from bar)
             then 'counting grade ' || g.counting_grade || ' is below ' || {{ p7_param('measured_min_grade', quote=true) }} || ' (limited by ' || lower(g.limiting_dimension) || ')'
        else 'counting grade ' || g.counting_grade
    end                                                                     as status_reason
from markets m
left join sourced s using (country_code)
left join grade g using (country_code)
left join proxy p using (country_code)
order by m.country_code
