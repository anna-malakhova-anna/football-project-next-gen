-- RESTRICTED (schema `linkage`). Candidates for coarsened exact matching, as (unit, event month e) pairs:
--   TREATED     each linked participant household at its own event time (first registration month), if it is not left-censored
--   COMPARISON  every unlinked account at EACH event month used by a treated household, as a candidate for a pseudo event time e
-- For every pair the pre period (months e-12 .. e-1, at least `fan_min_pre_months` with an account) gives the matching variables, and the post period
-- (months e .. e+11 inside the data, at least `fan_min_post_months`) gives the outcome. Everything is computed from engagement BEFORE e for matching, so
-- a comparison account is matched on what it looked like at that time, not on what it did afterwards.
-- Matching variables (all coarse): country, event month, pre-period tenure band, pre-period engagement band (quartile of the pre-period events per month,
-- pooled over all candidates). No ground truth is read here.
{% set pre = var('fan_pre_months') %}{% set min_pre = var('fan_min_pre_months') %}{% set post = var('fan_post_months') %}{% set min_post = var('fan_min_post_months') %}
with bounds as (

    select make_date(first_observed_year, 1, 1) as first_month, make_date(last_observed_year, 12, 1) as last_month
    from {{ ref('observation_window') }}

),

eng as (

    select account_id, date_diff('month', (select first_month from bounds), event_month) as mi, events
    from {{ ref('fct_household_engagement_month') }}

),

cum as (

    select account_id, mi, sum(events) over (partition by account_id order by mi) as cum_events from eng

),

created as (select account_id, min(mi) as created_mi from eng group by 1),

treated as (

    select t.account_id, t.household_id, t.first_registration_month as e, true as is_treated
    from {{ ref('int_participant_household_timeline') }} t where not t.is_left_censored

),

event_months as (select distinct e from treated),

comparison as (

    select a.account_id, cast(null as varchar) as household_id, m.e, false as is_treated
    from (select account_id from {{ ref('stg_fan_accounts') }}
          where account_id not in (select account_id from {{ ref('link_household_fan_account') }} where link_status = 'LINKED')) a
    cross join event_months m

),

pairs as (

    select *, date_diff('month', (select first_month from bounds), e) as e_mi,
           date_diff('month', (select first_month from bounds), (select last_month from bounds)) as last_mi
    from (select * from treated union all select * from comparison)

),

feat as (

    select
        p.account_id, p.household_id, p.is_treated, p.e, p.e_mi,
        greatest(0, p.e_mi - greatest(c.created_mi, p.e_mi - {{ pre }}))                              as pre_tenure_months,
        coalesce(cp.cum_events, 0) - coalesce(c0.cum_events, 0)                                       as pre_events,
        least(p.e_mi + {{ post }} - 1, p.last_mi) - p.e_mi + 1                                        as post_months,
        coalesce(cq.cum_events, 0) - coalesce(cp.cum_events, 0)                                       as post_events,
        a.country_code
    from pairs p
    join created c using (account_id)
    join {{ ref('stg_fan_accounts') }} a using (account_id)
    left join cum cp on cp.account_id = p.account_id and cp.mi = p.e_mi - 1
    left join cum c0 on c0.account_id = p.account_id and c0.mi = p.e_mi - {{ pre }} - 1
    left join cum cq on cq.account_id = p.account_id and cq.mi = least(p.e_mi + {{ post }} - 1, p.last_mi)

),

eligible as (

    select *,
           pre_events * 1.0 / pre_tenure_months                                                       as pre_rate,
           post_events * 1.0 / post_months                                                            as post_rate
    from feat
    where pre_tenure_months >= {{ min_pre }} and post_months >= {{ min_post }}

)

select
    account_id, household_id, is_treated, e, country_code,
    pre_tenure_months, pre_events, pre_rate, post_months, post_events, post_rate,
    case when pre_tenure_months >= {{ pre }} then '{{ pre }}' when pre_tenure_months >= 9 then '9-11' else '{{ min_pre }}-8' end as tenure_band,
    ntile(4) over (order by pre_rate, account_id, e)                                                   as pre_band
from eligible
