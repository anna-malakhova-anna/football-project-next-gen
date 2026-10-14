{{ config(tags=['phase5']) }}
-- Every field of the data standard is a column of the standardized records (so the validation can see it) and every column but the grp_* keys is a standard field (so nothing is
-- checked that the standard does not name). A STANDARD registry rule exists for each field and for no other.
with cols as (

    select lower(column_name) as field_name
    from information_schema.columns
    where table_schema = '{{ ref("dq_standardized_records").schema }}' and table_name = '{{ ref("dq_standardized_records").identifier }}' and lower(column_name) not like 'grp\_%' escape '\'

)

select 'standard field missing from the records' as problem, field_name from {{ ref('data_standard_fields') }} where field_name not in (select field_name from cols)
union all
select 'column not in the standard', field_name from cols where field_name not in (select field_name from {{ ref('data_standard_fields') }})
union all
select 'standard field without a registry rule', field_name from {{ ref('data_standard_fields') }}
where 'DQ-STD-' || upper(replace(field_name, '_', '-')) not in (select rule_id from {{ ref('dq_rule_registry') }} where origin = 'STANDARD')
union all
select 'STANDARD registry rule without a field', rule_id from {{ ref('dq_rule_registry') }}
where origin = 'STANDARD' and rule_id not in (select 'DQ-STD-' || upper(replace(field_name, '_', '-')) from {{ ref('data_standard_fields') }})
