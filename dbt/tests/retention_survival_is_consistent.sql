{{ config(tags=['phase4']) }}
-- Kaplan-Meier bookkeeping: the risk set shrinks by exactly the events and censorings of the step before; survival is within [0, 1], never rises,
-- and its interval brackets it; every spell has a defined outcome; age-outs and final-year censoring are never counted as churn.
select 'risk_set_not_conserved' as problem, segment_type || '|' || segment_value || '|' || cast(years_since_entry as varchar) as detail
from (
    select *, lag(at_risk) over w - lag(churn_events) over w - lag(censored_age_out) over w - lag(censored_final_year) over w as expected_at_risk,
              lag(years_since_entry) over w as prev_k
    from {{ ref('mart_retention_survival') }}
    window w as (partition by segment_type, segment_value order by years_since_entry)
)
where prev_k is not null and prev_k = years_since_entry - 1 and at_risk <> expected_at_risk
union all
select 'survival_out_of_range', segment_type || '|' || segment_value || '|' || cast(years_since_entry as varchar)
from {{ ref('mart_retention_survival') }} where survival < 0 or survival > 1 or ci_low > survival or survival > ci_high
union all
select 'survival_rises', segment_type || '|' || segment_value || '|' || cast(years_since_entry as varchar)
from (select *, lag(survival) over (partition by segment_type, segment_value order by years_since_entry) as prev_s
      from {{ ref('mart_retention_survival') }})
where prev_s is not null and survival > prev_s + 1e-9
union all
select 'spell_without_outcome', participant_id from {{ ref('retention_spells') }}
where outcome not in ('CHURNED', 'AGE_OUT', 'FINAL_YEAR') or duration_k < 0
union all
select 'age_out_counted_as_churn', participant_id from {{ ref('retention_spells') }}
where churned and youth_limit_k is not null and duration_k > youth_limit_k
union all
select 'event_beyond_observation', participant_id from {{ ref('retention_spells') }} where churned and duration_k > max_k_observed
union all
select 'entry_in_censored_first_year', participant_id from {{ ref('retention_spells') }}
where entry_year <= (select first_observed_year from {{ ref('observation_window') }})
