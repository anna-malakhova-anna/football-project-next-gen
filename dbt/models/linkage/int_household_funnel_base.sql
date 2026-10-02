-- RESTRICTED (schema `linkage`). One row per participant household with every funnel stage worked out, AS OF THE END OF ITS REGISTRATION COHORT YEAR (rework decision 4); windows come from fan_params.
-- Stages are cumulative and nested, in the spec's order:
--   linked       has a linked fan account (UNLINKED households never go past here: unknown is not a non-fan, but nothing about them is known either)
--   contactable  linked AND the account had at least one channel opted in at the as-of date (consent history, guardian account)
--   active       contactable AND engaged in the active window (default 90 days) before the as-of date
--   monetized    active AND at least one net purchase by the as-of date (a purchase that no refund reversed)
--   retained     monetized AND engaged in the active window ending 12 months after the first registration; only defined where that date is inside the data (`retention_observable`)
-- An account created after the as-of date has no consent yet, so it cannot be contactable at that date.
with s as (select * from {{ ref('fct_household_fan_status') }}),

girls as (

    select h.household_id, bool_or(p.sex = 'F') as has_girl
    from {{ ref('int_household') }} h join {{ ref('dim_participant') }} p using (participant_id)
    where p.is_minor_current or h.is_adult_household is false
    group by 1

),

at_date as (select s.*, (make_date(s.first_year, 12, 31) + interval 1 day)::timestamp as as_of from s),

contactable as (

    select distinct a.household_id
    from at_date a
    join {{ ref('fct_fan_consent_history') }} c on c.fan_account_id = a.fan_account_id
    where a.fan_status <> 'UNLINKED' and c.status = 'opt_in' and c.valid_from < a.as_of and (c.valid_to is null or c.valid_to >= a.as_of)

),

ev as (

    select x.fan_account_id, e.event_ts
    from {{ ref('stg_fan_events') }} e join {{ ref('int_fan_account_xref') }} x using (account_id)
    where not e.is_duplicate and 'orphan_event' <> all(e.dq_flags) and 'unmapped_event_type' <> all(e.dq_flags)

),

active as (

    select a.household_id,
           count(*) filter (where v.event_ts >= a.as_of - to_days({{ fan_param('active_window_days') }}) and v.event_ts < a.as_of) > 0 as active_at_asof,
           count(*) filter (where v.event_ts >= a.first_registration_month + to_months({{ fan_param('reactivation_window_months') }}) - to_days({{ fan_param('active_window_days') }})
                              and v.event_ts <  a.first_registration_month + to_months({{ fan_param('reactivation_window_months') }})) > 0 as active_12m_after
    from at_date a left join ev v on v.fan_account_id = a.fan_account_id
    where a.fan_status <> 'UNLINKED'
    group by 1

),

refunded as (select distinct original_txn_id as txn_id from {{ ref('fct_fan_transaction') }} where is_refund and is_in_net),

monetized as (

    select distinct a.household_id
    from at_date a
    join {{ ref('fct_fan_transaction') }} t on t.fan_account_id = a.fan_account_id
    where a.fan_status <> 'UNLINKED' and not t.is_refund and t.is_in_net and t.txn_ts < a.as_of
      and t.txn_id not in (select txn_id from refunded)

)

select
    a.household_id,
    a.first_year                                                            as cohort_year,
    a.is_left_censored,
    a.fan_status,
    m.is_team_market,
    coalesce(g.has_girl, false)                                             as is_girls_household,
    a.country_code not in ('US', 'CA')                                      as is_international,
    a.is_adult_household,
    (not a.is_adult_household) and a.participants >= 2                      as is_multi_child_household,
    a.post_window_complete                                                  as retention_observable,
    a.fan_status <> 'UNLINKED'                                              as st_linked,
    c.household_id is not null                                              as st_contactable_alone,
    coalesce(v.active_at_asof, false)                                       as st_active_alone,
    mo.household_id is not null                                             as st_monetized_alone,
    coalesce(v.active_12m_after, false)                                     as st_retained_alone
from at_date a
left join girls g using (household_id)
left join {{ ref('market_map') }} m on m.market_id = a.market_id
left join contactable c using (household_id)
left join active v using (household_id)
left join monetized mo using (household_id)
