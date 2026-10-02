-- RESTRICTED (schema `linkage`). For each LINKED participant household: the month its first registration is dated to, when it was active, and
-- when it churned. The first registration month is the registration period of the earliest registration (term -> month, var enrollment_month_by_term),
-- because most sources record no registration date. Households whose first registration is in the first data year are LEFT-CENSORED (the real first
-- registration may be earlier) and are not eligible for the before/after comparison.
--   churn_month   the first month after the last active season year, NULL while the household is still active in the last observed year
{% set months = var('enrollment_month_by_term') %}
with reg as (

    select h.household_id, u.season_year, u.season_term
    from {{ ref('int_household') }} h
    join {{ ref('bridge_registration_participant') }} b on b.participant_id = h.participant_id
    join {{ ref('int_registrations_unioned') }} u on u.registration_key = b.registration_key
    join {{ ref('fct_registration') }} f on f.registration_key = b.registration_key
    where f.is_valid_registration

),

ranked as (

    select household_id, season_year, season_term,
           row_number() over (partition by household_id order by season_year, {{ term_order('season_term') }}) as rn
    from reg

),

first_reg as (

    select household_id, season_year as first_year, season_term as first_term,
           make_date(season_year, case season_term {% for t, m in months.items() %}when '{{ t }}' then {{ m }} {% endfor %}end, 1) as first_registration_month
    from ranked where rn = 1

),

active as (

    select household_id, list_sort(list_distinct(list(season_year))) as active_years, max(season_year) as last_active_year
    from reg group by 1

)

select
    l.household_id,
    l.account_id,
    f.first_year,
    f.first_term,
    f.first_registration_month,
    f.first_year = {{ first_observed_year() }}                               as is_left_censored,
    a.active_years,
    a.last_active_year,
    case when a.last_active_year < (select last_observed_year from {{ ref('observation_window') }})
         then make_date(a.last_active_year + 1, 1, 1) end                   as churn_month
from (select household_id, account_id from {{ ref('link_household_fan_account') }} where link_status = 'LINKED') l
join first_reg f using (household_id)
join active a using (household_id)
