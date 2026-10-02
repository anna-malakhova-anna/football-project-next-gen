{{ config(tags=['phase4']) }}
-- Fan survival, lifetime value, activeness and RFM (rework spec 5.4): the same validity tests as player retention (survival within [0, 1], never rising, at risk shrinks by exactly the events
-- and censorings of the step before, the interval brackets it); every spell has an outcome; RFM quintiles hold about a fifth of the scored accounts each and every account has a named segment;
-- each activeness state is one of the defined states and an account is in exactly one per month; LTV is non-negative with low <= point <= high; person-time split adds up.
with s as (select * from {{ ref('mart_fan_survival') }})

select 'risk_set_not_conserved' as problem, fan_group || '|' || market_type || '|' || cast(months_since_origin as varchar) as detail
from (
    select *, lag(at_risk) over w - lag(lapses) over w - lag(censored) over w as expected, lag(months_since_origin) over w as prev_t
    from s window w as (partition by fan_group, market_type order by months_since_origin)
) where prev_t = months_since_origin - 1 and at_risk <> expected
union all
select 'survival_out_of_range', fan_group || '|' || market_type || '|' || cast(months_since_origin as varchar)
from s where survival < 0 or survival > 1 or ci_low > survival or survival > ci_high
union all
select 'survival_rises', fan_group || '|' || market_type || '|' || cast(months_since_origin as varchar)
from (select *, lag(survival) over (partition by fan_group, market_type order by months_since_origin) as prev_s from s) where prev_s is not null and survival > prev_s + 1e-9
union all
select 'spell_without_a_positive_time', fan_account_id from {{ ref('int_fan_lapse_spells') }} where t < 1 or t is null
union all
select 'ltv_not_ordered_or_negative', fan_group || '|' || market_type from {{ ref('mart_fan_ltv') }} where ltv < 0 or ltv_low > ltv + 1e-6 or ltv > ltv_high + 1e-6
union all
select 'rfm_quintile_not_a_fifth', cast(year as varchar) || '|' || cast(q as varchar)
from (select year, r_score as q, count(*) as n, sum(count(*)) over (partition by year) as total from {{ ref('int_fan_rfm_scores') }} group by year, r_score)
where abs(n - total / 5.0) > 1 + 0.001 * total
union all
select 'rfm_f_quintile_not_a_fifth', cast(year as varchar) || '|' || cast(q as varchar)
from (select year, f_score as q, count(*) as n, sum(count(*)) over (partition by year) as total from {{ ref('int_fan_rfm_scores') }} group by year, f_score)
where abs(n - total / 5.0) > 1 + 0.001 * total
union all
select 'rfm_m_quintile_not_a_fifth', cast(year as varchar) || '|' || cast(q as varchar)
from (select year, m_score as q, count(*) as n, sum(count(*)) over (partition by year) as total from {{ ref('int_fan_rfm_scores') }} group by year, m_score)
where abs(n - total / 5.0) > 1 + 0.001 * total
union all
select 'scored_account_without_a_segment', cast(r.year as varchar) || '|' || r.fan_account_id
from {{ ref('int_fan_rfm_scores') }} r left join {{ ref('rfm_segment_map') }} m on m.r_score = r.r_score and m.fm_score = cast(floor((r.f_score + r.m_score) / 2.0 + 0.5) as integer)
where m.segment is null
union all
select 'activeness_unknown_state', from_state from {{ ref('mart_fan_activeness') }} where section = 'STATE' and from_state not in ('ACTIVE', 'AT_RISK', 'LAPSED', 'NEW')
union all
select 'activeness_state_counts_differ_from_accounts_present', cast(event_month as varchar)
from (select event_month, sum(accounts) as n from {{ ref('mart_fan_activeness') }} where section = 'STATE' group by 1) a
join (select event_month, count(*) as n_present from {{ ref('fct_fan_engagement_month') }} group by 1) b using (event_month) where a.n <> b.n_present
union all
select 'child_churn_person_time_has_no_rows', 'mart_fan_lapse_after_child_churn' from (select count(*) as n from {{ ref('mart_fan_lapse_after_child_churn') }}) where n <> 2
