{{ config(tags=['phase4']) }}
-- EXEC share: where is consent captured? The opt-in rate by channel for each capture point (signup, checkout, flag registration, preference center) and for other cuts of the consent lines.
-- A consent line is the latest recorded status per account and channel; no record is NOT a "no" and is not in the denominator. AGGREGATE ONLY (restricted `linkage` schema, ADR-009).
with src as (

    select cut as consent_cut, dimension_value as consent_dimension_value, channel as consent_channel, consent_lines, opt_ins as consent_opt_ins, opt_in_rate as consent_opt_in_rate
    from {{ ref('mart_consent_capture') }}
    where reliable

)

select consent_cut, consent_dimension_value, consent_channel, consent_lines, consent_opt_ins, consent_opt_in_rate, suppressed
from {{ suppress_small_cells('src', ['consent_cut', 'consent_dimension_value', 'consent_channel'], ['consent_lines', 'consent_opt_ins'],
        rates={'consent_opt_in_rate': ['consent_lines', 'consent_opt_ins']}) }}
order by consent_cut, consent_dimension_value, consent_channel
