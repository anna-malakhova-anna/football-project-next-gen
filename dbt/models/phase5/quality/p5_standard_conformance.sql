-- depends_on: {{ ref('p5_data_standard') }}
-- Every feed against the data standard, field by field: share of rows present and valid. The validation SQL itself is the p5_standard_check macro, so it applies to any new feed.
with checked as (

    {{ p5_standard_check(ref('p5_standardized_records'), 'feed') }}

)

select
    feed,
    field_name,
    requirement,
    n_rows,
    n_missing,
    n_invalid,
    round(1 - (n_missing + n_invalid)::double / n_rows, 4)                  as conformance,
    1 - (n_missing + n_invalid)::double / n_rows >= (select value::double from {{ ref('p5_params') }} where param = 'standard_min_conformance') as meets
from checked
