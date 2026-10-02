-- RESTRICTED (schema `linkage`). Event study: engagement by month relative to event time (-12 to +18) for matched participant households and their
-- weighted matched comparison accounts. Event time is the first registration month for a household and the matched household's event time for its
-- comparisons (pseudo event time). A flat pre period (k < 0) supports the design; the post period shows the effect and, for households that churn,
-- its decay. Only months that exist in the data are used. effect_pct = treated mean / comparison mean - 1 at each k (matched on the pre-period level,
-- so a ratio is read as a relative difference); `diff` is the plain difference in events per household-month with an approximate standard error.
{% set pre = var('fan_pre_months') %}
with m as (select * from {{ ref('int_fan_cem_matched') }}),

ks as (select unnest(range(-{{ pre }}, 19)) as k),

obs as (

    select
        ks.k, m.is_treated, m.account_id, m.e, m.weight,
        f.events
    from m
    cross join ks
    join {{ ref('fct_household_engagement_month') }} f
      on f.account_id = m.account_id and f.event_month = (m.e + to_months(ks.k))::date

),

v as (

    select
        o.k, o.is_treated,
        sum(o.weight * o.events) / sum(o.weight)                            as mean_events,
        sum(o.weight)                                                       as w,
        sum(o.weight * o.weight)                                            as w2,
        count(*)                                                            as n
    from obs o group by 1, 2

),

var_part as (

    select o.k, o.is_treated,
           sum(o.weight * o.weight * power(o.events - v.mean_events, 2)) / power(v.w, 2) as var_mean
    from obs o join v using (k, is_treated)
    group by o.k, o.is_treated, v.w

)

select
    t.k                                                                     as months_since_event,
    t.n                                                                     as treated_households,
    c.n                                                                     as comparison_pairs,
    round(t.mean_events, 5)                                                 as treated_mean_events,
    round(c.mean_events, 5)                                                 as comparison_mean_events,
    round(t.mean_events - c.mean_events, 5)                                 as diff,
    round(sqrt(tv.var_mean + cv.var_mean), 5)                               as diff_se,
    round(t.mean_events / c.mean_events - 1, 5)                             as effect_pct,
    '{{ var("methodology_version") }}'                                      as methodology_version
from v t
join v c on c.k = t.k and not c.is_treated
join var_part tv on tv.k = t.k and tv.is_treated
join var_part cv on cv.k = c.k and not cv.is_treated
where t.is_treated
order by t.k
