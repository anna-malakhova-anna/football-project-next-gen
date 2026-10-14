{{ config(tags=['phase5']) }}
-- Data quality fitness per purpose for each minimization variant. Label-free: the share of registrations (the three modelled sources) fit for each purpose when the variant is applied to
-- the data as received. Two honest limits, both set in the seed minimization_variants:
--   * a rule that needs a field at a precision the variant no longer holds (the cross-record day-level DOB check; the well-formedness of an email that is only a hash) can no longer be
--     evaluated. It stops failing records, so the fitness can only rise or stay level: this is lost DETECTION, not gained quality. The column `rules_no_longer_evaluable` says how many.
--   * a hashed email cannot reach a guardian, so ACTIVATE fitness is zero by construction (activate_possible is false).
-- Flag-based rules (impossible DOB, unparseable DOB, division-only DOB) judge the value at collection and are taken as unchanged.
with v as (

    select variant_id, sort_order, label,
           coalesce(string_split(nullif(unevaluable_rules, ''), '|'), cast([] as varchar[])) as dropped,
           email_treatment <> 'HASH' as activate_possible
    from {{ ref('minimization_variants') }}

),

f as (

    select source_system, failing_rules_count, failing_rules_segment, failing_rules_geo, failing_rules_retain, failing_rules_activate
    from {{ ref('dq_record_fitness') }}
    where source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED')

)

select
    v.variant_id, v.sort_order, v.label,
    count(*)                                                                as records,
    round(avg(case when len(list_filter(f.failing_rules_count,    r -> not list_contains(v.dropped, r))) = 0 then 1.0 else 0.0 end), 4) as fit_for_count,
    round(avg(case when len(list_filter(f.failing_rules_segment,  r -> not list_contains(v.dropped, r))) = 0 then 1.0 else 0.0 end), 4) as fit_for_segment,
    round(avg(case when len(list_filter(f.failing_rules_geo,      r -> not list_contains(v.dropped, r))) = 0 then 1.0 else 0.0 end), 4) as fit_for_geo,
    round(avg(case when len(list_filter(f.failing_rules_retain,   r -> not list_contains(v.dropped, r))) = 0 then 1.0 else 0.0 end), 4) as fit_for_retain,
    round(avg(case when not v.activate_possible then 0.0
                   when len(list_filter(f.failing_rules_activate, r -> not list_contains(v.dropped, r))) = 0 then 1.0 else 0.0 end), 4) as fit_for_activate,
    len(any_value(v.dropped))                                               as rules_no_longer_evaluable
from v cross join f
group by 1, 2, 3
