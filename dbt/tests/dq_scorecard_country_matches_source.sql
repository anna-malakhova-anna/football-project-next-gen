{{ config(tags=['phase7']) }}
-- dq_scorecard_country copies dq_scorecard_source's method, grouped by country (ADR-025). For a source that covers exactly one country (Canada's
-- CA_CLUB, the US league), both must agree on every score and grade, so the two models cannot drift apart unnoticed.
with one_country as (
    select source_system, min(country_code) as country_code from {{ ref('dq_scorecard_country') }} group by 1 having count(distinct country_code) = 1
)
select s.source_system, s.season_year, s.purpose, s.dimension, s.score as source_score, c.score as country_score, s.grade as source_grade, c.grade as country_grade
from {{ ref('dq_scorecard_source') }} s
join one_country o using (source_system)
left join {{ ref('dq_scorecard_country') }} c on c.source_system = s.source_system and c.country_code = o.country_code
     and c.season_year = s.season_year and c.purpose = s.purpose and c.dimension = s.dimension
where c.score is distinct from s.score or c.grade is distinct from s.grade
