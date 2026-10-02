{{ config(tags=['phase4']) }}
-- Matched difference-in-differences design: every matched treated household has at least one comparison in its stratum; comparison weights add up to the
-- treated count of each stratum; comparisons are never linked households; treated households are never left-censored; the matching variables are
-- identical within a stratum by construction (a stratum is defined by them) and the pre period is measured before event time.
with m as (select * from {{ ref('int_fan_cem_matched') }})

select 'treated_without_comparison' as problem, account_id as detail
from m t where is_treated
  and not exists (select 1 from m c where not c.is_treated and (c.country_code, c.e, c.tenure_band, c.pre_band) = (t.country_code, t.e, t.tenure_band, t.pre_band))
union all
select 'comparison_weights_do_not_sum_to_treated_count', country_code || '|' || cast(e as varchar) || '|' || tenure_band || '|' || cast(pre_band as varchar)
from m group by country_code, e, tenure_band, pre_band
having abs(sum(weight) filter (where not is_treated) - count(*) filter (where is_treated)) > 1e-6
union all
select 'comparison_is_a_linked_household', account_id
from m where not is_treated and account_id in (select account_id from {{ ref('link_household_fan_account') }} where link_status = 'LINKED')
union all
select 'treated_is_left_censored', account_id
from m where is_treated and account_id in (select account_id from {{ ref('int_participant_household_timeline') }} where is_left_censored)
union all
select 'event_time_is_not_the_first_registration_month', account_id
from m where is_treated and e <> (select first_registration_month from {{ ref('int_participant_household_timeline') }} t where t.account_id = m.account_id)
union all
select 'too_little_history', account_id || '|' || cast(e as varchar)
from m where pre_tenure_months < {{ var('fan_min_pre_months') }} or post_months < {{ var('fan_min_post_months') }}
union all
select 'event_study_pre_period_missing', cast(months_since_event as varchar)
from (select unnest(range(-{{ var('fan_pre_months') }}, 19)) as months_since_event) k
where months_since_event not in (select months_since_event from {{ ref('mart_fan_did') }})
union all
select 'match_rate_below_90pct', cast(match_rate as varchar)
from {{ ref('mart_fan_outcomes_summary') }} where estimator = 'DID_ADDITIVE' and match_rate < 0.90
