-- Kaplan-Meier retention by segment, in SQL, from retention_spells (which holds the censoring rules).
--   at_risk      entrants observed AND youth-eligible at step k whose first gap has not yet happened
--   churn_events entrants whose first gap is at step k
--   censored_*   entrants whose follow-up stopped after step k without an event: AGE_OUT (left the youth age range) or FINAL_YEAR (unknown future)
--   hazard       events / at_risk
--   survival     S(k) = product over j <= k of (1 - events_j / at_risk_j), computed as exp(sum(ln(...))) over the steps
--   greenwood_se S(k) * sqrt(sum events_j / (at_risk_j * (at_risk_j - events_j)))   (Greenwood's formula)
--   ci_low/high  S(k) +/- 1.96 * se, clipped to [0, 1] (the plain linear interval; it is wide where few players remain at risk)
-- Segments are the entrant's attributes at entry. Entrants with an unknown age cannot be tested for age-out and are left out of every segment.
-- `reliable` = at least k_min entrants at risk: below that, do not read the curve.
{% set kmin = privacy_param('k_min') %}
with s as (select * from {{ ref('retention_spells') }} where age_known),

seg as (

    select 'ALL' as segment_type, 'ALL' as segment_value, duration_k, outcome from s
    union all select 'sex', entry_sex, duration_k, outcome from s
    union all select 'entry_age_band', entry_age_band, duration_k, outcome from s
    union all select 'entry_country', entry_country, duration_k, outcome from s
    union all select 'multi_org_at_entry', case when entry_multi_org then 'MULTI_ORG' else 'SINGLE_ORG' end, duration_k, outcome from s
    union all select 'entry_division', entry_division, duration_k, outcome from s

),

ks as (select unnest(range(1, (select last_observed_year - first_observed_year + 1 from {{ ref('observation_window') }}))) as k),

sizes as (select segment_type, segment_value, count(*) as n_entrants from seg group by 1, 2),

steps as (

    select
        g.segment_type, g.segment_value, ks.k,
        count(*) filter (where g.duration_k >= ks.k)                                       as at_risk,
        count(*) filter (where g.duration_k = ks.k and g.outcome = 'CHURNED')              as churn_events,
        count(*) filter (where g.duration_k = ks.k and g.outcome = 'AGE_OUT')              as censored_age_out,
        count(*) filter (where g.duration_k = ks.k and g.outcome = 'FINAL_YEAR')           as censored_final_year
    from seg g cross join ks
    group by 1, 2, 3

),

live as (select * from steps where at_risk > 0),

km as (

    select
        *,
        churn_events * 1.0 / at_risk                                                       as hazard,
        bool_or(churn_events >= at_risk) over w                                            as reached_zero,
        sum(ln(greatest(1 - churn_events * 1.0 / at_risk, 1e-12))) over w                  as log_s,
        sum(case when at_risk > churn_events then churn_events * 1.0 / (at_risk * (at_risk - churn_events)) else 0 end) over w as greenwood_sum
    from live
    window w as (partition by segment_type, segment_value order by k)

)

select
    km.segment_type,
    km.segment_value,
    z.n_entrants,
    km.k                                                                                   as years_since_entry,
    km.at_risk,
    km.churn_events,
    km.censored_age_out,
    km.censored_final_year,
    round(km.hazard, 6)                                                                    as hazard,
    round(case when km.reached_zero then 0 else exp(km.log_s) end, 6)                      as survival,
    round(case when km.reached_zero then 0 else exp(km.log_s) * sqrt(km.greenwood_sum) end, 6) as greenwood_se,
    round(greatest(0, (case when km.reached_zero then 0 else exp(km.log_s) end)
                      - 1.96 * (case when km.reached_zero then 0 else exp(km.log_s) * sqrt(km.greenwood_sum) end)), 6) as ci_low,
    round(least(1, (case when km.reached_zero then 0 else exp(km.log_s) end)
                   + 1.96 * (case when km.reached_zero then 0 else exp(km.log_s) * sqrt(km.greenwood_sum) end)), 6)   as ci_high,
    km.at_risk >= {{ kmin }}                                                               as reliable,
    '{{ var("methodology_version") }}'                                                     as methodology_version
from km
join sizes z using (segment_type, segment_value)
order by segment_type, segment_value, km.k
