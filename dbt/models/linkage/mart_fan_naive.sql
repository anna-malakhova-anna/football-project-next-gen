-- RESTRICTED (schema `linkage`). THE WRONG ANSWER, computed on purpose (two versions, Phase 6: see below): average engagement of participant households versus non-participant fan households
-- over the same months. Every linked household counts from its first registration month onward; the comparison is the average unlinked account in the SAME
-- calendar months. Households that enroll a child are fans to begin with (selection), so this mixes the effect of the program with who joins it: it is
-- biased upward, and it is shown next to the matched estimate so the gap is visible.
-- Ratio estimator: naive = sum of treated mean events / sum of the matching comparison mean events - 1, with a delta-method standard error over households.
-- NAIVE_EXISTING (the companion shown beside the matched estimate): the same comparison restricted to households that ALREADY had a fan account before registering (fan status other than NET_NEW), which is
-- the kind of household the matched estimate describes. Selection overstates it, as designed: those households were already more engaged before they enrolled.
-- NAIVE (pooled, analyst detail only): every linked household, INCLUDING accounts the programme itself created (NET_NEW). Those households are less engaged than the average fan (the programme draws in
-- low-fandom households), so pooling them pulls the average DOWN. Its direction is therefore not the direction of the selection bias; the composition, not a tuning problem, explains why it can sit below the matched estimate.
with cm as (

    select event_month, avg(events) as comparison_mean from {{ ref('fct_household_engagement_month') }} where not is_linked group by 1

),

t as (

    select
        f.account_id,
        s.fan_status not in ('NET_NEW', 'UNLINKED')                         as is_existing,
        avg(f.events)                                                       as x,
        avg(cm.comparison_mean)                                             as y,
        count(*)                                                            as months
    from {{ ref('fct_household_engagement_month') }} f
    join {{ ref('int_participant_household_timeline') }} tl on tl.account_id = f.account_id
    join {{ ref('fct_household_fan_status') }} s on s.household_id = tl.household_id
    join cm on cm.event_month = f.event_month
    where f.event_month >= tl.first_registration_month
    group by f.account_id, s.fan_status not in ('NET_NEW', 'UNLINKED')

)

{% for est, cond in [('NAIVE', 'true'), ('NAIVE_EXISTING', 'is_existing')] %}
{{ 'union all' if not loop.first }}
select
    '{{ est }}'                                                             as estimator,
    round(r.ratio - 1, 5)                                                   as estimate_pct,
    round((r.ratio - 1) - 1.96 * sqrt(r.v / r.n) / r.ybar, 5)               as ci_low_pct,
    round((r.ratio - 1) + 1.96 * sqrt(r.v / r.n) / r.ybar, 5)               as ci_high_pct,
    r.n                                                                     as treated_households,
    (select count(*) from {{ ref('dim_fan_account') }}) - r.n              as comparison_units,
    '{{ var("methodology_version") }}'                                      as methodology_version
from (
    select sum(x) / sum(y) as ratio, count(*) as n, avg(y) as ybar,
           var_samp(x - (select sum(x) / sum(y) from t where {{ cond }}) * y) as v
    from t where {{ cond }}
) r
{% endfor %}
