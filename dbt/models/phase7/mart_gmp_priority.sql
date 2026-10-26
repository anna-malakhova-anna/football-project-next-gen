-- Market prioritization (Phase 7, spec section 9; Anna's decision D5: the same method as the data products page). Four dimensions, 1 to 5 (privacy_risk:
-- 5 is riskiest), priority = value + feasibility + readiness - privacy risk, as in product_prioritization.
--   suggested_*  the DRAFT score from the rubric (gmp_priority_rubric): value from clubs with rights (+1 if new to the program), feasibility from the
--                market's status (and whether a national federation exists), readiness from the counting grade, privacy risk from what the market
--                sends or would send (record-level INTL_FED / CA_CLUB rows, or the aggregate minimum return) and its assumed regime. Nothing here is typed
--                per market.
--   final scores Anna's score where she has set one (gmp_market_priority_overrides), else the draft; score_status says which.
with status as (select * from {{ ref('mart_gmp_market_status') }}),

rubric as (select * from {{ ref('gmp_priority_rubric') }}),

federation as (

    select country_code, bool_or(federation_exists) as federation_exists
    from {{ ref('stg_gmp_proxy') }}
    where not is_superseded and season_year = (select last_observed_year from {{ ref('observation_window') }})
    group by 1

),

keys as (

    select s.country_code, s.clubs_with_rights, s.status_on_page = 'NEW' as is_new, s.status, s.counting_grade, s.participation_source, s.output_port, s.legal_regime_id,
           case when s.status = 'PROXY_ONLY' and coalesce(f.federation_exists, false) then 'PROXY_ONLY_WITH_FEDERATION' else s.status end as feasibility_key,
           coalesce(s.counting_grade, 'NONE') as readiness_key,
           case when s.participation_source in ('INTL_FED', 'CA_CLUB') and s.output_port = 'global_eu_uk' then 'RECORD_LEVEL_EU_UK_CH'   -- player-level sources
                when s.participation_source in ('INTL_FED', 'CA_CLUB') then 'RECORD_LEVEL_OTHER'
                when s.legal_regime_id = 'CN_PIPL' then 'REGIME_CN_PIPL'
                else 'AGGREGATE_ONLY' end as privacy_key
    from status s left join federation f using (country_code)

),

suggested as (

    select k.*,
           least(5, (select max(r.score) from rubric r where r.dimension = 'value_to_goals' and r.rule = 'clubs_with_rights' and r.min_value <= k.clubs_with_rights)
                    + case when k.is_new then (select r.score from rubric r where r.rule = 'new_in_program_bonus') else 0 end) as suggested_value_to_goals,
           (select r.score from rubric r where r.dimension = 'feasibility_today' and r.rule = k.feasibility_key)  as suggested_feasibility_today,
           (select r.score from rubric r where r.dimension = 'data_readiness' and r.rule = k.readiness_key)       as suggested_data_readiness,
           (select r.score from rubric r where r.dimension = 'privacy_risk' and r.rule = k.privacy_key)          as suggested_privacy_risk
    from keys k

),

overrides as (

    select country_code,
           max(case when dimension = 'value_to_goals' then score end)    as set_value_to_goals,
           max(case when dimension = 'feasibility_today' then score end) as set_feasibility_today,
           max(case when dimension = 'data_readiness' then score end)    as set_data_readiness,
           max(case when dimension = 'privacy_risk' then score end)      as set_privacy_risk
    from {{ ref('gmp_market_priority_overrides') }} group by 1

),

final as (

    select s.*,
           coalesce(o.set_value_to_goals, s.suggested_value_to_goals)       as value_to_goals,
           coalesce(o.set_feasibility_today, s.suggested_feasibility_today) as feasibility_today,
           coalesce(o.set_data_readiness, s.suggested_data_readiness)       as data_readiness,
           coalesce(o.set_privacy_risk, s.suggested_privacy_risk)           as privacy_risk,
           case when o.country_code is null then 'DRAFT' else 'SET_BY_ANNA' end as score_status
    from suggested s left join overrides o using (country_code)

)

select
    f.country_code, f.status, f.counting_grade, f.clubs_with_rights, f.is_new,
    f.suggested_value_to_goals, f.suggested_feasibility_today, f.suggested_data_readiness, f.suggested_privacy_risk,
    f.value_to_goals, f.feasibility_today, f.data_readiness, f.privacy_risk,
    f.value_to_goals + f.feasibility_today + f.data_readiness - f.privacy_risk as priority_score,
    rank() over (order by f.value_to_goals + f.feasibility_today + f.data_readiness - f.privacy_risk desc, f.country_code) as priority_rank,
    f.score_status,
    (select r.rationale from rubric r where r.dimension = 'feasibility_today' and r.rule = f.feasibility_key) || '. '
        || (select r.rationale from rubric r where r.dimension = 'privacy_risk' and r.rule = f.privacy_key) || '.' as rationale
from final f
order by priority_rank
