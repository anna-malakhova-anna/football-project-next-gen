{{ config(tags=['phase5']) }}
-- CLUB share: why can a club not reach more families? The activation funnel per club market and year, each step's loss split into DATA QUALITY and PRIVACY (consent), in households (fractional: a household
-- is allocated across markets by ZIP3 weight). Aggregates only; no household, child or contact key.
-- Suppression: a step is hidden when its own count, or the step before it, is below k_min, because a published loss next to a hidden count would give the count back by subtraction.
{% set k = privacy_param('k_min') %}
with f as (

    select participation_year, market_id as club_market_id, step_no, step, unit, n, lost_dq, lost_privacy, loss_type,
           lag(n) over (partition by participation_year, market_id order by step_no) as previous_n
    from {{ ref('mart_activation_funnel') }}

)

select
    participation_year, club_market_id, step_no, step, unit,
    case when n >= {{ k }} and coalesce(previous_n, n) >= {{ k }} then round(n, 1) end as funnel_count,
    case when n >= {{ k }} and coalesce(previous_n, n) >= {{ k }} then round(lost_dq, 1) end as funnel_lost_dq,
    case when n >= {{ k }} and coalesce(previous_n, n) >= {{ k }} then round(lost_privacy, 1) end as funnel_lost_privacy,
    case when n >= {{ k }} and coalesce(previous_n, n) >= {{ k }} then loss_type end as loss_type,
    case when n >= {{ k }} and coalesce(previous_n, n) >= {{ k }} then 'NONE' else 'PRIMARY' end as suppressed
from f
order by participation_year, club_market_id, step_no
