{{ config(tags=['phase3']) }}
-- The analyst share carries no direct identifier and no date of birth, the pseudonym is a salted 64-hex hash that is not
-- the participant id, it is one row per participant-year, and one participant keeps one key across years.
select 'forbidden_column' as problem, column_name as detail
from information_schema.columns
where table_schema = 'share_analyst'
  and (lower(column_name) like '%name%' or lower(column_name) like '%email%' or lower(column_name) like '%phone%'
       or lower(column_name) like '%dob%' or lower(column_name) = 'postal_code' or lower(column_name) like '%participant_id%'
       or lower(column_name) like '%source_person%' or lower(column_name) like '%organization%' or lower(column_name) like 'consent%')
union all
select 'key_not_64_hex', analyst_key from {{ ref('share_analyst__participant_year') }}
where not regexp_matches(analyst_key, '^[0-9a-f]{64}$')
union all
select 'key_is_a_raw_participant_id', a.analyst_key
from {{ ref('share_analyst__participant_year') }} a join {{ ref('dim_participant') }} d on d.participant_id = a.analyst_key
union all
select 'grain_not_one_row_per_participant_year', cast(count(*) as varchar)
from {{ ref('share_analyst__participant_year') }}
having count(*) <> (select count(*) from {{ ref('fct_participant_year') }})
   or count(distinct analyst_key || '|' || participation_year) <> count(*)
union all
select 'postal_prefix_longer_than_policy', postal_prefix from {{ ref('share_analyst__participant_year') }}
where length(postal_prefix) > {{ privacy_param('postal_prefix_len') }}
union all
select 'birth_year_not_a_year', cast(birth_year as varchar) from {{ ref('share_analyst__participant_year') }}
where birth_year is not null and (birth_year < 1900 or birth_year > 2100)
