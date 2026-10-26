{{ config(tags=['phase7']) }}
-- EXEC share (DP6, spec section 7): the counting quality of each program market with a participation source, season by season, so the tab can show
-- whether a market is getting easier or harder to read. Clubs appear only as counts. From DP4's dq_scorecard_country (COUNT purpose).
select
    s.country_code, m.country_name, s.season_year,
    s.score                                                                 as counting_score,
    s.grade                                                                 as counting_grade,
    s.limiting_dimension,
    s.known_orgs                                                            as clubs_known,
    s.reporting_orgs                                                        as clubs_filed
from {{ ref('dq_scorecard_country') }} s
join {{ ref('gmp_markets') }} m using (country_code)
where s.purpose = 'COUNT' and s.dimension = 'PURPOSE_SCORE'
order by s.country_code, s.season_year
