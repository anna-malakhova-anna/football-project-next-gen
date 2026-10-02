-- RESTRICTED (schema `linkage`). THE WRONG ANSWER, computed on purpose: average engagement of participant households versus non-participant fan households
-- over the same months. Every linked household counts from its first registration month onward; the comparison is the average unlinked account in the SAME
-- calendar months. Households that enroll a child are fans to begin with (selection), so this mixes the effect of the program with who joins it: it is
-- biased upward, and it is shown next to the matched estimate so the gap is visible.
-- Ratio estimator: naive = sum of treated mean events / sum of the matching comparison mean events - 1, with a delta-method standard error over households.
with cm as (

    select event_month, avg(events) as comparison_mean from {{ ref('fct_household_engagement_month') }} where not is_linked group by 1

),

t as (

    select
        f.account_id,
        avg(f.events)                                                       as x,
        avg(cm.comparison_mean)                                             as y,
        count(*)                                                            as months
    from {{ ref('fct_household_engagement_month') }} f
    join {{ ref('int_participant_household_timeline') }} tl on tl.account_id = f.account_id
    join cm on cm.event_month = f.event_month
    where f.event_month >= tl.first_registration_month
    group by 1

),

r as (select sum(x) / sum(y) as ratio, count(*) as n, avg(y) as ybar from t)

select
    'NAIVE'                                                                 as estimator,
    round(r.ratio - 1, 5)                                                   as estimate_pct,
    round((r.ratio - 1) - 1.96 * sqrt(var_samp(t.x - r.ratio * t.y) / r.n) / r.ybar, 5) as ci_low_pct,
    round((r.ratio - 1) + 1.96 * sqrt(var_samp(t.x - r.ratio * t.y) / r.n) / r.ybar, 5) as ci_high_pct,
    r.n                                                                     as treated_households,
    (select count(*) from {{ ref('dim_fan_account') }}) - r.n              as comparison_units,
    '{{ var("methodology_version") }}'                                      as methodology_version
from t cross join r
group by r.ratio, r.n, r.ybar
