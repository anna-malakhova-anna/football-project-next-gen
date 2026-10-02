{{ config(tags=['phase4']) }}
-- GROUND TRUTH (evaluation only). The value-uplift estimates (mart_fan_value_uplift) against the effect the generator knows, per status group and outcome, over exactly the matched participant
-- households and their post months. The generator records, per participant account and month, the expected events and the expected NET spend by category as observed and with no programme
-- (fan_effect_truth), so the truth is (sum observed - sum no programme) / sum no programme. Engagement TYPES other than the total have no oracle (the uplift multiplies all events, and the flag
-- content share is a relabel), so their truth is NULL. Nothing here feeds back into the design.
{% set post = var('fan_post_months') %}
with m as (

    select m.account_id, date_diff('month', make_date((select first_observed_year from {{ ref('observation_window') }}), 1, 1), m.e) as e_mi, m.post_months, g.status_group
    from {{ ref('int_fan_cem_matched') }} m
    join (select t.account_id, case when s.fan_status in ('EXISTING_ACTIVE', 'EXISTING_COOLING') then 'EXISTING' else 'LAPSED' end as status_group
          from {{ ref('fct_household_fan_status') }} s join {{ ref('int_participant_household_timeline') }} t using (household_id) where t.is_linked) g on g.account_id = m.account_id
    where m.is_treated

),

o as (

    select m.status_group, t.*
    from m join {{ source('ground_truth', 'fan_effect_truth') }} t on t.account_id = m.account_id and t.month_idx >= m.e_mi and t.month_idx < m.e_mi + m.post_months
    union all
    select 'ALL', t.*
    from m join {{ source('ground_truth', 'fan_effect_truth') }} t on t.account_id = m.account_id and t.month_idx >= m.e_mi and t.month_idx < m.e_mi + m.post_months

),

truth as (

    select status_group, 'events' as outcome, (sum(expected_events_observed) - sum(expected_events_no_programme)) / sum(expected_events_no_programme) as truth_pct,
           (sum(expected_events_observed) - sum(expected_events_no_programme)) / count(*) as truth_per_month from o group by 1
    {% for c in ['ticket', 'merch', 'subscription', 'other'] %}
    union all select status_group, 'net_spend_{{ c }}', (sum(expected_spend_{{ c }}_observed) - sum(expected_spend_{{ c }}_no_programme)) / nullif(sum(expected_spend_{{ c }}_no_programme), 0),
           (sum(expected_spend_{{ c }}_observed) - sum(expected_spend_{{ c }}_no_programme)) / count(*) from o group by 1
    {% endfor %}
    union all select status_group, 'net_spend_total',
        (sum(expected_spend_ticket_observed + expected_spend_merch_observed + expected_spend_subscription_observed + expected_spend_other_observed)
         - sum(expected_spend_ticket_no_programme + expected_spend_merch_no_programme + expected_spend_subscription_no_programme + expected_spend_other_no_programme))
        / nullif(sum(expected_spend_ticket_no_programme + expected_spend_merch_no_programme + expected_spend_subscription_no_programme + expected_spend_other_no_programme), 0),
        (sum(expected_spend_ticket_observed + expected_spend_merch_observed + expected_spend_subscription_observed + expected_spend_other_observed)
         - sum(expected_spend_ticket_no_programme + expected_spend_merch_no_programme + expected_spend_subscription_no_programme + expected_spend_other_no_programme)) / count(*)
    from o group by 1

)

select
    u.status_group, u.outcome, u.outcome_kind, u.treated_households, u.pct_is_stable,
    u.did_per_month, u.did_ci_low_per_month, u.did_ci_high_per_month,
    round(t.truth_per_month, 5)                                             as truth_per_month,
    round(u.did_per_month - t.truth_per_month, 5)                           as did_error_per_month,
    t.truth_per_month between u.did_ci_low_per_month and u.did_ci_high_per_month as truth_in_ci_per_month,
    u.did_pct, u.did_ci_low_pct, u.did_ci_high_pct, u.naive_pct,
    round(t.truth_pct, 5)                                                   as truth_pct,
    round(u.did_pct - t.truth_pct, 5)                                       as did_error_pct,
    round(u.naive_pct - t.truth_pct, 5)                                     as naive_error_pct
from {{ ref('mart_fan_value_uplift') }} u
left join truth t using (status_group, outcome)
order by u.status_group, u.outcome_kind, u.outcome
