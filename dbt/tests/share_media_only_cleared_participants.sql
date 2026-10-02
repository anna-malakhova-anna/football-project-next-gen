{{ config(tags=['phase3']) }}
-- The media roster means "cleared": re-derived independently from dim_participant and fct_registration, the roster must
-- contain exactly the participant x org x season rows whose most recent captured photo consent is TRUE (and no open
-- integrity issue). NULL (not captured) and FALSE are never on the list.
with expected as (

    select distinct d.first_name, d.last_name, f.organization_id, f.participation_year as season_year, f.season_term
    from {{ ref('fct_registration') }} f
    join {{ ref('dim_participant') }} d on d.participant_id = f.participant_id
    where f.is_valid_registration and d.consent_photo is true and not d.has_open_integrity_issue

),

got as (select distinct first_name, last_name, organization_id, season_year, season_term from {{ ref('share_media__roster') }})

select 'cleared_but_missing' as problem, e.first_name || ' ' || e.last_name as detail
from expected e left join got g using (first_name, last_name, organization_id, season_year, season_term) where g.first_name is null
union all
select 'on_roster_without_clearance', g.first_name || ' ' || g.last_name
from got g left join expected e using (first_name, last_name, organization_id, season_year, season_term) where e.first_name is null
union all
select 'consent_flag_not_true', first_name || ' ' || last_name from {{ ref('share_media__roster') }} where consent_photo is not true
union all
select 'forbidden_column', column_name from information_schema.columns
where table_schema = 'share_media'
  and (lower(column_name) like '%dob%' or lower(column_name) like '%email%' or lower(column_name) like '%phone%'
       or lower(column_name) in ('birth_year', 'sex', 'participant_id', 'postal_code', 'contact_email'))
union all
-- a participant whose photo consent was never captured (or was refused) must not appear under their own name+org+season
select 'uncleared_participant_on_roster', d.first_name || ' ' || d.last_name
from {{ ref('dim_participant') }} d
join {{ ref('fct_registration') }} f on f.participant_id = d.participant_id and f.is_valid_registration
join {{ ref('share_media__roster') }} r on r.first_name = d.first_name and r.last_name = d.last_name
  and r.organization_id = f.organization_id and r.season_year = f.participation_year and r.season_term = f.season_term
where d.consent_photo is not true
  and not exists (   -- unless a DIFFERENT person with the same name, org and season really is cleared
      select 1 from {{ ref('dim_participant') }} d2
      join {{ ref('fct_registration') }} f2 on f2.participant_id = d2.participant_id and f2.is_valid_registration
      where d2.participant_id <> d.participant_id and d2.first_name = d.first_name and d2.last_name = d.last_name
        and f2.organization_id = f.organization_id and f2.participation_year = f.participation_year
        and f2.season_term = f.season_term and d2.consent_photo is true and not d2.has_open_integrity_issue)
