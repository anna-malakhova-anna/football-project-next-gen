-- The market Now/Next/Later board (Phase 7, spec section 9), in the style of the Phase 6 roadmap: one card per program market with its lane, action and
-- gate from gmp_market_roadmap (a DRAFT until Anna sets it), its priority from mart_gmp_priority, and the gate's current value, status and bar fill
-- computed here from the data, never typed:
--   COUNTING_GRADE_AT_LEAST  the counting score against the lowest score of the target grade band
--   MIN_RETURN_SEASONS       seasons in which a participation source filed for the market (0 when the market has none: a known zero)
--   PROXY_RETURN             1 when clubs filed a proxy return for the market in the latest season, else 0
-- gate_status is MET, NOT_YET, or PENDING when the value the gate needs is missing (never shown as 0).
with roadmap as (select * from {{ ref('gmp_market_roadmap') }}),

status as (select * from {{ ref('mart_gmp_market_status') }}),

seasons as (

    select country_code, count(distinct season_year) filter (where reporting_orgs > 0) as seasons_filed
    from {{ ref('dq_scorecard_country') }} where purpose = 'COUNT' and dimension = 'PURPOSE_SCORE' group by 1

),

proxy as (

    select country_code, count(*) > 0 as proxy_filed
    from {{ ref('stg_gmp_proxy') }}
    where not is_superseded and season_year = (select last_observed_year from {{ ref('observation_window') }})
    group by 1

),

valued as (

    select r.country_code, r.lane, r.action, r.gate_kind, r.target, r.status as plan_status, r.rationale,
           s.country_name, s.status, s.counting_grade, s.clubs_with_rights, p.priority_rank, p.priority_score, p.score_status,
           case r.gate_kind
               when 'COUNTING_GRADE_AT_LEAST' then s.counting_score
               when 'MIN_RETURN_SEASONS' then coalesce(se.seasons_filed, case when s.participation_source is null then 0 end)
               when 'PROXY_RETURN' then case when coalesce(x.proxy_filed, false) then 1 else 0 end
           end::double as current_value,
           case r.gate_kind
               when 'COUNTING_GRADE_AT_LEAST' then (select min_score from {{ ref('dq_grade_bands') }} b where b.grade = r.target)
               else try_cast(r.target as double)
           end as target_value
    from roadmap r
    join status s using (country_code)
    join {{ ref('mart_gmp_priority') }} p using (country_code)
    left join seasons se using (country_code)
    left join proxy x using (country_code)

)

select
    country_code, country_name, lane, action, gate_kind, target, status, counting_grade, clubs_with_rights,
    priority_rank, priority_score, score_status, plan_status, rationale,
    current_value, target_value,
    case when current_value is null then 'PENDING' when current_value >= target_value then 'MET' else 'NOT_YET' end as gate_status,
    case when current_value is null or target_value is null or target_value = 0 then null else round(least(100, 100 * current_value / target_value), 1) end as bar_fill_pct
from valued
order by case lane when 'NOW' then 1 when 'NEXT' then 2 when 'LATER' then 3 else 4 end, priority_rank
