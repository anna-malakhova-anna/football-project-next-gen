{{ config(tags=['phase5']) }}
-- The control limits are ordered, the first season of an entity has no history and so no flag, and a flag means the score is outside the limits AS PUBLISHED, exactly: the model decides
-- the flag on the rounded limits it shows. (This used to allow 0.011 of rounding either way, which also required a score 0.01 below the shown limit, and truly below the unrounded one, NOT
-- to be flagged: it failed on correct flags, e.g. a score of 57.14 against a limit of 57.15. The unit test dq_trend_flag_agrees_with_the_published_limits covers the score ON the limit.)
select entity_type, entity_id, season_year, purpose, 'limits out of order' as problem from {{ ref('dq_trend') }} where lcl is not null and lcl > ucl
union all
select entity_type, entity_id, season_year, purpose, 'a point with no history is flagged' from {{ ref('dq_trend') }} where prior_seasons = 0 and (out_of_control or direction is not null)
union all
select entity_type, entity_id, season_year, purpose, 'flag disagrees with the limits' from {{ ref('dq_trend') }}
where prior_seasons >= 1 and out_of_control is distinct from (score < lcl or score > ucl)
union all
select entity_type, entity_id, season_year, purpose, 'direction disagrees with the flag' from {{ ref('dq_trend') }}
where out_of_control <> (direction is not null)
