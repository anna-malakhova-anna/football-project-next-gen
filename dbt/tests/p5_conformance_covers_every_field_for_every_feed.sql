{{ config(tags=['phase5']) }}
-- One conformance row per feed x standard field; counts are consistent; the mixed Pop Warner feed shows its tackle rows as invalid program_type and the flag-only feeds show none.
select 'wrong row count' as problem
where (select count(*) from {{ ref('p5_standard_conformance') }}) <> (select count(*) from {{ ref('p5_data_standard') }}) * (select count(distinct feed) from {{ ref('p5_standardized_records') }})
union all
select 'counts exceed rows' from {{ ref('p5_standard_conformance') }} where n_missing + n_invalid > n_rows
union all
select 'tackle rows not flagged' where (select n_invalid from {{ ref('p5_standard_conformance') }} where feed = 'pop_warner_feed' and field_name = 'program_type') = 0
union all
select 'unexpected program_type problem in ' || feed from {{ ref('p5_standard_conformance') }} where field_name = 'program_type' and feed <> 'pop_warner_feed' and n_invalid > 0
