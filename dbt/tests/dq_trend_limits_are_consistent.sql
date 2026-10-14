{{ config(tags=['phase5']) }}
-- The control limits are ordered, the first season of an entity has no history and so no flag, and a flag means the score really is outside the limits.
select entity_type, entity_id, season_year, purpose, 'limits out of order' as problem from {{ ref('dq_trend') }} where lcl is not null and lcl > ucl
union all
select entity_type, entity_id, season_year, purpose, 'a point with no history is flagged' from {{ ref('dq_trend') }} where prior_seasons = 0 and (out_of_control or direction is not null)
union all
select entity_type, entity_id, season_year, purpose, 'flag disagrees with the limits' from {{ ref('dq_trend') }}
where prior_seasons >= 1 and out_of_control <> (score < lcl - 0.011 or score > ucl + 0.011)
union all
select entity_type, entity_id, season_year, purpose, 'direction disagrees with the flag' from {{ ref('dq_trend') }}
where out_of_control <> (direction is not null)
