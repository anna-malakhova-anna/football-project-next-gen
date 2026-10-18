{{ config(schema='phase6') }}
-- DP5 (flag-to-fan conversion insights), aggregate only. Household-level funnel split by the age tier of the household's YOUNGEST child (the most restrictive child governs, ADR-022). Counts of households:
--   1 registered household              analytics only
--   2 linked to a fan account           analytics only (permitted under the household linkage policy, ADR-009)
--   3 engaged                           analytics only: linked and active in the 90 days before the as-of date
--   4 purchased                         analytics only: engaged and at least one net purchase
--   5 consented to club marketing       ACTIVATION: the guardian's CLUB_MARKETING permission is Y (int_consent_permissions); counted among all registered households, not only purchasers
-- Steps 2 to 4 are nested; step 5 is not nested in them. No child, household or contact key leaves the restricted zone: tiers and counts only. A step is hidden when its count, or the count of the step it
-- follows, is below k_min (a published loss next to a hidden count would give the count back by subtraction); zero is shown.
-- Analytics is not activation: steps 1 to 4 describe linked households and move no one into a contact list; only step 5 uses consent.
{% set k = privacy_param('k_min') %}
with perm as (

    select household_id, governing_tier as age_tier, permitted from {{ ref('int_consent_permissions') }} where purpose = 'CLUB_MARKETING'

),

h as (

    select p.age_tier,
           true                                                             as registered,
           coalesce(b.st_linked, false)                                     as linked,
           coalesce(b.st_linked and b.st_active_alone, false)               as engaged,
           coalesce(b.st_linked and b.st_active_alone and b.st_monetized_alone, false) as purchased,
           p.permitted = 'Y'                                                as consented
    from perm p left join {{ ref('int_household_funnel_base') }} b on b.household_id = p.household_id

),

long as (

    select age_tier, 1 as step_no, 'registered household' as step, 'ANALYTICS_ONLY' as kind, count(*) filter (where registered) as n from h group by 1
    union all select age_tier, 2, 'linked to a fan account', 'ANALYTICS_ONLY', count(*) filter (where linked) from h group by 1
    union all select age_tier, 3, 'engaged', 'ANALYTICS_ONLY', count(*) filter (where engaged) from h group by 1
    union all select age_tier, 4, 'purchased', 'ANALYTICS_ONLY', count(*) filter (where purchased) from h group by 1
    union all select age_tier, 5, 'consented to club marketing', 'ACTIVATION', count(*) filter (where consented) from h group by 1

),

f as (

    select *, lag(n) over (partition by age_tier order by step_no) as previous_n,
           max(case when step_no = 1 then n end) over (partition by age_tier) as registered_n
    from long

)

select
    age_tier, step_no, step, kind,
    case when n >= {{ k }} and coalesce(case when step_no = 5 then registered_n else previous_n end, n) >= {{ k }} then n end as households,
    case when n >= {{ k }} and coalesce(case when step_no = 5 then registered_n else previous_n end, n) >= {{ k }} and registered_n > 0 then round(1.0 * n / registered_n, 4) end as share_of_registered,
    case when n >= {{ k }} and coalesce(case when step_no = 5 then registered_n else previous_n end, n) >= {{ k }} then 'NONE' else 'PRIMARY' end as suppressed
from f
order by case age_tier when 'U13' then 1 when '13_15' then 2 when '16_17' then 3 when 'ADULT' then 4 else 5 end, step_no
