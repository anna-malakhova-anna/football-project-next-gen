{{ config(tags=['phase5']) }}
-- Every field of the data standard is a column of the standardized records (so the check can see it) and every column but `feed` is a standard field (so nothing is collected that the standard does not name).
with cols as (

    select lower(column_name) as field_name
    from information_schema.columns
    where table_schema = '{{ ref("p5_standardized_records").schema }}' and table_name = '{{ ref("p5_standardized_records").identifier }}' and lower(column_name) <> 'feed'

)

select 'standard field missing from the records' as problem, field_name from {{ ref('p5_data_standard') }} where field_name not in (select field_name from cols)
union all
select 'column not in the standard', field_name from cols where field_name not in (select field_name from {{ ref('p5_data_standard') }})
