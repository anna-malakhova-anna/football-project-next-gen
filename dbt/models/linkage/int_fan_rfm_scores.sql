-- RESTRICTED (schema `linkage`; account-level scores, never shared). RFM scores of fan accounts at the end of each year, over the trailing `rfm_trailing_months` (default 12): recency (months
-- since the last engagement or purchase), frequency (months with any engagement) and monetary (net spend, synthetic currency), each as a QUINTILE by NTILE(5) over the scored accounts (5 = best).
-- A score is only given to an account with some activity in the window. Ties are broken deterministically (monetary ties, mostly zeros, by engagement then account id), so each quintile holds
-- a fifth of the accounts. mart_fan_rfm turns the scores into named segments and compares the mix across fan groups.
with years as (select unnest(range(first_observed_year, last_observed_year + 1)) as year from {{ ref('observation_window') }}),

base as (

    select y.year, f.fan_account_id,
           sum(f.events) as events,
           count(*) filter (where f.is_active_month) as active_months,
           max(case when f.is_active_month then f.event_month end) as last_active_month
    from years y
    join {{ ref('fct_fan_engagement_month') }} f
      on f.event_month > make_date(y.year, 12, 1) - to_months({{ fan_param('rfm_trailing_months') }}) and f.event_month <= make_date(y.year, 12, 1)
    group by 1, 2

),

spend as (

    select y.year, t.fan_account_id, sum(t.signed_amount) as net_spend, max(t.txn_month) as last_txn_month
    from years y
    join {{ ref('fct_fan_transaction') }} t
      on t.txn_month > make_date(y.year, 12, 1) - to_months({{ fan_param('rfm_trailing_months') }}) and t.txn_month <= make_date(y.year, 12, 1)
    where t.is_in_net
    group by 1, 2

),

scored_in as (

    select
        b.year, b.fan_account_id,
        date_diff('month', greatest(coalesce(b.last_active_month, date '1900-01-01'), coalesce(s.last_txn_month, date '1900-01-01')), make_date(b.year, 12, 1)) as recency_months,
        b.active_months                                                     as frequency,
        coalesce(s.net_spend, 0)                                            as monetary,
        b.events
    from base b left join spend s using (year, fan_account_id)
    where b.active_months > 0 or s.fan_account_id is not null

),

scores as (

    select *,
           ntile(5) over (partition by year order by recency_months desc, fan_account_id)                  as r_score,
           ntile(5) over (partition by year order by frequency, events, fan_account_id)                    as f_score,
           ntile(5) over (partition by year order by monetary, events, fan_account_id)                     as m_score
    from scored_in

)

select
    year,
    fan_account_id,
    recency_months, frequency, monetary, r_score, f_score, m_score,
    cast(floor((f_score + m_score) / 2.0 + 0.5) as integer)                 as fm_score
from scores
