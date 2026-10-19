-- DP1 AGGREGATE PORT. Where the registrations with a missing value concentrate: per season and KPI, the count of records by organization (from the record-level quality base) and by division
-- (from the conformed registrations). Counts only: no person or record key leaves DP1. Read by mart_missingness_bias (DP3) for its top-organizations and top-divisions columns.
--   girls_share_of_youth  records with a missing gender (organization side) / unknown sex on a minor, exact duplicates excluded (division side)
--   age_band_mix          records with only an age group (organization side) / no birth year (division side)
select season_year as participation_year, 'girls_share_of_youth' as kpi, 'ORGANIZATION' as item_type, org_id as item, count(*) as n
from {{ ref('dq_record_base') }} where list_contains(dq_flags, 'missing_gender') and source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') group by all
union all
select season_year, 'age_band_mix', 'ORGANIZATION', org_id, count(*)
from {{ ref('dq_record_base') }} where list_contains(dq_flags, 'dob_age_group_only') and source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') group by all
union all
select season_year, 'girls_share_of_youth', 'DIVISION', coalesce(canonical_division, 'UNMAPPED'), count(*)
from {{ ref('int_registrations_unioned') }} where sex = 'U' and coalesce(is_minor, false) and not coalesce(is_exact_duplicate, false) group by all
union all
select season_year, 'age_band_mix', 'DIVISION', coalesce(canonical_division, 'UNMAPPED'), count(*)
from {{ ref('int_registrations_unioned') }} where birth_year is null and not coalesce(is_exact_duplicate, false) group by all
