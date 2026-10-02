-- Seed lookups are matched case-insensitively on trimmed keys, so the keys must be unique that way.
-- Returns offending keys; the test passes when no rows come back.
select 'division_map' as seed, source_system || '|' || lower(trim(source_label)) as key, count(*) as n
from {{ ref('division_map') }} group by 2 having count(*) > 1
union all
select 'country_map', lower(trim(source_value)), count(*)
from {{ ref('country_map') }} group by 2 having count(*) > 1
union all
select 'gender_map', lower(trim(source_value)), count(*)
from {{ ref('gender_map') }} group by 2 having count(*) > 1
