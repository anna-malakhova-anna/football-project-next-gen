-- RESTRICTED (schema `linkage`). One row per participant household: its FAN STATUS as of the month of its first registration (rework spec 4.2). The windows come from fan_params.
--
--   UNLINKED             no linked fan account. UNKNOWN, NOT "non-fan": the household may well be a fan under a different email. It is never reclassified into any other status.
--   NET_NEW              a linked account created on or after the first registration month
--   EXISTING_ACTIVE      a linked account created earlier, with engagement in the active window (default 90 days) before the registration month
--   EXISTING_COOLING     (an addition to the spec's table, which leaves a gap) engagement in the lapsed window (default 180 days) but none in the active window: neither active nor lapsed
--   LAPSED_REACTIVATED   linked, created earlier, no engagement in the lapsed window, engagement within the reactivation window (default 12 months) after
--   LAPSED_DORMANT       linked, created earlier, no engagement in the lapsed window, none after
--   INSUFFICIENT_HISTORY (an addition) linked and created earlier, no engagement seen, but the lapsed window is not fully observed (before the data starts) or the account is younger than it:
--                        "no engagement" cannot be told from "not yet looked"
-- A status is exhaustive and exclusive: exactly one per household. Households whose first registration is in the first data year are LEFT-CENSORED (the true first registration may be
-- earlier): the flag is kept and they are not used for the before/after comparison. `post_window_complete` says whether the reactivation window ends inside the data.
-- The registration month is dated from the term of the first registration (var enrollment_month_by_term), not a registration date.
with tl as (select * from {{ ref('int_participant_household_timeline') }}),

p as (select household_id, market_id, country_code, participants, is_adult_household, years_span from {{ ref('int_household_profile') }}),

d as (select fan_account_id, first_created_at, acquisition_source from {{ ref('dim_fan_account') }}),

ev as (

    select x.fan_account_id, e.event_ts
    from {{ ref('stg_fan_events') }} e
    join {{ ref('int_fan_account_xref') }} x using (account_id)
    where not e.is_duplicate and 'orphan_event' <> all(e.dq_flags) and 'unmapped_event_type' <> all(e.dq_flags)

),

bounds as (select make_date(first_observed_year, 1, 1) as first_day, make_date(last_observed_year, 12, 31) as last_day from {{ ref('observation_window') }}),

base as (

    select
        tl.household_id,
        tl.account_id                                                       as fan_account_id,
        tl.is_linked,
        tl.first_registration_month                                         as e,
        tl.first_year,
        tl.is_left_censored,
        d.first_created_at,
        d.acquisition_source
    from tl left join d on d.fan_account_id = tl.account_id

),

counts as (

    select
        b.household_id,
        count(*) filter (where v.event_ts >= b.e - to_days({{ fan_param('active_window_days') }}) and v.event_ts < b.e)                         as events_in_active_window,
        count(*) filter (where v.event_ts >= b.e - to_days({{ fan_param('lapsed_window_days') }}) and v.event_ts < b.e)                         as events_in_lapsed_window,
        count(*) filter (where v.event_ts >= b.e and v.event_ts < b.e + to_months({{ fan_param('reactivation_window_months') }}))              as events_in_reactivation_window
    from base b left join ev v on v.fan_account_id = b.fan_account_id
    where b.is_linked
    group by 1

)

select
    b.household_id,
    b.e                                                                     as first_registration_month,
    b.first_year,
    b.is_left_censored,
    b.fan_account_id,
    b.first_created_at                                                      as account_created_at,
    b.acquisition_source,
    case
        when not b.is_linked then 'UNLINKED'
        when b.first_created_at >= b.e then 'NET_NEW'
        when c.events_in_active_window > 0 then 'EXISTING_ACTIVE'
        when c.events_in_lapsed_window > 0 then 'EXISTING_COOLING'
        when b.e - to_days({{ fan_param('lapsed_window_days') }}) < (select first_day from bounds)
             or b.first_created_at > b.e - to_days({{ fan_param('lapsed_window_days') }}) then 'INSUFFICIENT_HISTORY'
        when c.events_in_reactivation_window > 0 then 'LAPSED_REACTIVATED'
        else 'LAPSED_DORMANT'
    end                                                                     as fan_status,
    b.is_linked and b.first_created_at >= b.e and b.acquisition_source = 'flag_registration_prompt' as net_new_via_flag_prompt,
    c.events_in_active_window,
    c.events_in_lapsed_window,
    c.events_in_reactivation_window,
    b.e + to_months({{ fan_param('reactivation_window_months') }}) <= (select last_day from bounds) as post_window_complete,
    p.market_id,
    p.country_code,
    p.participants,
    p.is_adult_household,
    p.years_span
from base b
left join counts c using (household_id)
join p using (household_id)
