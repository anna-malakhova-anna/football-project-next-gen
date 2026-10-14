{{ config(schema='phase5') }}
-- AGGREGATE (counts only; safe to show). The funnel from participants to households eligible for club activation, with the reason for each drop.
--   1 participants                        resolved children (the child side)
--   2 children in a contactable household children whose registrations carry a usable parent email
--   3 resolved households                 parent-side units (siblings share one; two parent emails join into one)
--   4 households with known provenance    at least one consent event whose WHAT, WHEN and WHICH WORDING are all known       <- the data quality story
--   5 households eligible for activation  an explicit NFL_CLUB_MARKETING grant with the provenance activation requires        <- the privacy story
-- Rows 1 and 2 count children; rows 3 to 5 count households. No identifier is output.
with stages as (

    select 1 as stage, 'participants' as stage_name, 'children' as unit, count(distinct p5_person_id) as n from {{ ref('p5_record_person') }}
    union all
    select 2, 'children in a contactable household', 'children', count(distinct p5_person_id) from {{ ref('p5_household_child') }}
    union all
    select 3, 'resolved households', 'households', count(*) from (select distinct household_id from {{ ref('p5_household') }})
    union all
    select 4, 'households with known consent provenance', 'households', count(distinct household_id) from {{ ref('p5_consent_event') }} where household_id is not null and provenance_known
    union all
    select 5, 'households eligible for club activation', 'households', count(*) from {{ ref('p5_household_activation') }} where eligible_for_club_activation

)

select
    stage, stage_name, unit, n,
    n - lag(n) over (order by stage)                                        as change_from_previous,
    round(n::double / nullif(lag(n) over (order by stage), 0), 4)           as share_of_previous,
    case stage
        when 2 then 'children whose registrations have no usable parent email (school rosters, blank or malformed emails) cannot be reached'
        when 3 then 'units change from children to households'
        when 4 then 'consent missing, or recorded without a timestamp or a wording: nobody can say what the parent agreed to, when, on which text'
        when 5 then 'no explicit club-marketing opt-in, an opt-in declined, or an opt-in without a timestamp or wording. A consent email is not a marketing opt-in.'
    end                                                                     as why_households_drop
from stages
