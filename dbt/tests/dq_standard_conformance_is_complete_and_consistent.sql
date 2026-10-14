{{ config(tags=['phase5']) }}
-- One conformance row per source x organization x season x standard field; counts add up; and the mixed Pop Warner feed shows its tackle rows as an invalid program_type while the
-- flag-only sources show none.
select 'wrong row count' as problem
where (select count(*) from {{ ref('dq_standard_conformance') }}) <>
      (select count(*) from {{ ref('data_standard_fields') }}) * (select count(*) from (select distinct grp_source_system, grp_org_id, grp_season_year from {{ ref('dq_standardized_records') }}))
union all
select 'counts exceed rows' from {{ ref('dq_standard_conformance') }} where n_missing + n_invalid > n_rows
union all
select 'tackle rows not flagged' where (select sum(n_invalid) from {{ ref('dq_standard_conformance') }} where source_system = 'pop_warner_feed' and field_name = 'program_type') = 0
union all
select distinct 'unexpected program_type problem in ' || source_system from {{ ref('dq_standard_conformance') }}
where field_name = 'program_type' and source_system <> 'pop_warner_feed' and n_invalid > 0
