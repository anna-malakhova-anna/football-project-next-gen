-- One row per source x column of the staged, common-schema data: row count, null rate, distinct count,
-- top values and parse-failure rate. Pure SQL: UNPIVOT over a Jinja column list.
-- Top values are suppressed for identifiers and quasi-identifiers (names, contact details, dates of
-- birth, postal codes, record ids): a profile should not republish them, even for synthetic data.
{% set columns = [
    'source_record_id', 'source_person_id', 'season_label', 'season_year', 'season_term',
    'organization_id', 'organization_name', 'country_code', 'region_code',
    'first_name', 'last_name', 'first_name_key', 'last_name_key',
    'dob', 'dob_parse_status', 'birth_year', 'dob_precision', 'sex', 'age_at_cutoff',
    'canonical_division', 'is_minor', 'contact_email', 'contact_phone', 'postal_code',
    'consent_photo', 'consent_marketing', 'registered_at'
] %}
{% set suppressed = [
    'source_record_id', 'source_person_id', 'first_name', 'last_name', 'first_name_key', 'last_name_key',
    'dob', 'contact_email', 'contact_phone', 'postal_code', 'registered_at'
] %}

with base as (

    {% for model in ['stg_us_registrations', 'stg_ca_registrations', 'stg_intl_registrations'] -%}
    select source_system, raw_postal,
    {%- for c in columns %} cast({{ c }} as varchar) as {{ c }}{{ ',' if not loop.last }}{% endfor %}
    from {{ ref(model) }}
    {% if not loop.last %}union all by name{% endif %}
    {% endfor %}

),

ordinals as (

    select * from (values
    {%- for c in columns %} ('{{ c }}', {{ loop.index }}){{ ',' if not loop.last }}{% endfor %}
    ) as t(column_name, column_position)

),

long as (

    select source_system, column_name, val
    from base
    unpivot include nulls (val for column_name in ({{ columns | join(', ') }}))

),

stats as (

    select
        source_system,
        column_name,
        count(*)                                                            as row_count,
        count(*) - count(val)                                               as null_count,
        count(distinct val)                                                 as distinct_count
    from long
    group by 1, 2

),

freq as (

    select source_system, column_name, val, count(*) as n,
           row_number() over (partition by source_system, column_name order by count(*) desc, val) as rnk
    from long
    where val is not null
    group by 1, 2, 3

),

top as (

    select source_system, column_name,
           list(val || ' (' || n || ')' order by rnk)                       as top_values
    from freq
    where rnk <= 5
    group by 1, 2

),

failures as (

    -- a value was present in the source but could not be turned into a usable one
    select source_system, 'dob' as column_name,
           count(*) filter (where dob_parse_status in ('AMBIGUOUS', 'UNPARSEABLE'))       as failures,
           count(*) filter (where dob_parse_status <> 'BLANK')                            as attempts
    from {{ ref('stg_us_registrations') }} group by 1
    union all
    select source_system, 'dob',
           count(*) filter (where dob_parse_status in ('AMBIGUOUS', 'UNPARSEABLE')),
           count(*) filter (where dob_parse_status <> 'BLANK')
    from {{ ref('stg_intl_registrations') }} group by 1
    union all
    select source_system, 'dob',
           count(*) filter (where dob_parse_status = 'UNPARSEABLE'),
           count(*)
    from {{ ref('stg_ca_registrations') }} group by 1
    union all
    select source_system, 'postal_code',
           count(*) filter (where postal_code is null),
           count(*)
    from {{ ref('stg_us_registrations') }} where raw_postal is not null and trim(raw_postal) <> '' group by 1
    union all
    select source_system, 'postal_code',
           count(*) filter (where postal_code is null),
           count(*)
    from {{ ref('stg_ca_registrations') }} where raw_postal is not null group by 1

)

select
    s.source_system,
    o.column_position,
    s.column_name,
    s.row_count,
    s.null_count,
    round(s.null_count * 1.0 / s.row_count, 4)                              as null_rate,
    s.distinct_count,
    case when s.column_name in ({{ suppressed | map('tojson') | join(', ') | replace('"', "'") }})
         then null else t.top_values end                                    as top_values,
    s.column_name in ({{ suppressed | map('tojson') | join(', ') | replace('"', "'") }})
                                                                            as top_values_suppressed,
    round(f.failures * 1.0 / nullif(f.attempts, 0), 4)                      as parse_failure_rate
from stats s
join ordinals o using (column_name)
left join top t using (source_system, column_name)
left join failures f using (source_system, column_name)
order by s.source_system, o.column_position
