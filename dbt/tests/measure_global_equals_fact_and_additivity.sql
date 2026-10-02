{{ config(tags=['phase3']) }}
-- Additivity (rule C6) and engine consistency, per year. Returns problems; passes when empty.
--   * global unique participants = rows of fct_participant_year for that year
--   * global unique participants = sum of participants_attributed over countries (the additive view)
--   * sum of participants_present - global unique participants = extra countries played (and equals the number of
--     multi-country participants when nobody plays in three or more countries)
--   * global registrations = sum of registrations over countries
with g as (select * from {{ ref('mart_participation_global') }}),
c as (
    select participation_year, sum(participants_attributed) as attributed, sum(participants_present) as present, sum(registrations) as registrations
    from {{ ref('mart_participation_by_country') }} group by 1
),
f as (
    select participation_year, count(*) as rows_,
           count(*) filter (where is_multi_country) as multi_country,
           sum(len(countries_played) - 1) as extra_countries,
           max(len(countries_played)) as max_countries
    from {{ ref('fct_participant_year') }} group by 1
)
select 'global_not_fact_rows' as problem, g.participation_year, g.unique_participants as got, f.rows_ as expected
from g join f using (participation_year) where g.unique_participants <> f.rows_
union all
select 'attributed_does_not_sum_to_global', g.participation_year, c.attributed, g.unique_participants
from g join c using (participation_year) where c.attributed <> g.unique_participants
union all
select 'present_minus_global_not_extra_countries', g.participation_year, c.present - g.unique_participants, f.extra_countries
from g join c using (participation_year) join f using (participation_year) where c.present - g.unique_participants <> f.extra_countries
union all
select 'present_minus_global_not_multi_country_count', g.participation_year, c.present - g.unique_participants, f.multi_country
from g join c using (participation_year) join f using (participation_year)
where f.max_countries <= 2 and c.present - g.unique_participants <> f.multi_country
union all
select 'global_multi_country_not_fact', g.participation_year, g.multi_country_participants, f.multi_country
from g join f using (participation_year) where g.multi_country_participants <> f.multi_country
union all
select 'registrations_not_additive', g.participation_year, c.registrations, g.registrations
from g join c using (participation_year) where c.registrations <> g.registrations
union all
select 'present_not_greater_when_multi_country_exists', g.participation_year, c.present, g.unique_participants
from g join c using (participation_year) join f using (participation_year)
where f.multi_country > 0 and c.present <= g.unique_participants
