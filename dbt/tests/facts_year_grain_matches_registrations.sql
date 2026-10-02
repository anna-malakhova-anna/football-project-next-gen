{{ config(tags=['phase3']) }}
-- fct_participant_year has exactly one row for every participant-year with a valid registration and nothing else;
-- its registration counts add up to the valid registrations; every registration has exactly one participant.
select 'participant_years_differ' as problem, cast(f.n as varchar) as got, cast(r.n as varchar) as expected
from (select count(*) n from {{ ref('fct_participant_year') }}) f,
     (select count(*) n from (select distinct participant_id, participation_year from {{ ref('fct_registration') }} where is_valid_registration)) r
where f.n <> r.n
union all
select 'valid_registrations_differ', cast(f.n as varchar), cast(r.n as varchar)
from (select sum(valid_registration_count) n from {{ ref('fct_participant_year') }}) f,
     (select count(*) n from {{ ref('fct_registration') }} where is_valid_registration) r
where f.n <> r.n
union all
select 'us_season_registrations_differ', cast(f.n as varchar), cast(r.n as varchar)
from (select sum(valid_registration_count) n from {{ ref('fct_participant_us_season') }}) f,
     (select count(*) n from {{ ref('fct_registration') }} where is_valid_registration and us_season_term is not null) r
where f.n <> r.n
union all
select 'registration_count_differs', cast(f.n as varchar), cast(r.n as varchar)
from (select count(*) n from {{ ref('fct_registration') }}) f, (select count(*) n from {{ ref('int_registrations_unioned') }}) r
where f.n <> r.n
