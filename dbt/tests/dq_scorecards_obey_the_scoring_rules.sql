{{ config(tags=['phase5']) }}
-- depends_on: {{ ref('privacy_params') }}
-- ADR-014 scoring rules, re-derived independently from the long-form results, for both scorecards:
--   * every score is in [0, 100] and its grade is the band the seed says (graded on the Wilson lower bound where the interval applies)
--   * the PURPOSE_SCORE is the MINIMUM of its dimension scores, so it is <= each of them (averaging would hide a failing link)
--   * a sample below dq_n_min always carries an interval and is graded on its lower bound; a sample at or above it carries none
--   * the interval brackets the score
with org as (select 'ORG' as level, source_system || '|' || org_id as entity, season_year, purpose, dimension, score, score_interval_low as lo, score_interval_high as hi, interval_applied, grade, record_count from {{ ref('dq_scorecard_org') }}),

src as (select 'SOURCE' as level, source_system as entity, season_year, purpose, dimension, score, score_interval_low as lo, score_interval_high as hi, interval_applied, grade, record_count from {{ ref('dq_scorecard_source') }}),

s as (select * from org union all select * from src)

select level, entity, season_year, purpose, dimension, 'score out of range' as problem from s where score < 0 or score > 100
union all
select level, entity, season_year, purpose, dimension, 'grade does not match the band'
from s where grade <> (select b.grade from {{ ref('dq_grade_bands') }} b where b.min_score <= (case when interval_applied then coalesce(lo, score) else score end) order by b.min_score desc limit 1)
union all
select p.level, p.entity, p.season_year, p.purpose, d.dimension, 'purpose score above a dimension score'
from s p join (select * from s where dimension <> 'PURPOSE_SCORE') d using (level, entity, season_year, purpose)
where p.dimension = 'PURPOSE_SCORE' and p.score > d.score + 0.011
union all
select level, entity, season_year, purpose, dimension, 'small sample without an interval, or large with one'
from s where interval_applied <> (record_count < {{ privacy_param('dq_n_min') }}) or (interval_applied and record_count > 0 and (lo is null or hi is null)) or (not interval_applied and (lo is not null or hi is not null))
union all
select level, entity, season_year, purpose, dimension, 'interval does not bracket the score' from s where interval_applied and lo is not null and (lo > score + 0.011 or hi < score - 0.011)
