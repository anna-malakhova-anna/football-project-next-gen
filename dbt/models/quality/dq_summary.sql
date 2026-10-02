-- One row per source x defect: OBSERVED (what the SQL pipeline flagged) vs CONFIGURED (what the generator
-- injected, from config/generation.yaml via the dq_defect_config seed).
-- status: OK                   observed within +/-50% (relative) of the configured rate, or exact for counts
--         OUT_OF_TOLERANCE     detectable defect whose observed rate is off by more than 50%
--         NOT_DETECTABLE_PHASE1  needs identity matching or a second source (Phase 2); observed is NULL
--         NOT_CONFIGURED       flagged by the pipeline but never injected and not in the config catalog
{% set tolerance = 0.5 %}
with observed as (

    select source_system, flag as defect_id, count(*) as observed_count
    from {{ ref('dq_defect_log') }}
    group by 1, 2

),

denominators as (

    -- what each configured rate is a share of, measured on the staged data
    select source_system, 'rows' as denominator_kind, count(*) as denominator from {{ ref('int_registrations_unioned') }} group by 1
    union all
    select source_system, 'rows', count(*) from {{ ref('stg_school_headcounts') }} group by 1
    union all
    select 'FAN_ENGAGEMENT', 'events', count(*) from {{ ref('stg_fan_events') }}
    union all
    select 'FAN_ENGAGEMENT', 'accounts', count(*) from {{ ref('stg_fan_accounts') }}
    union all
    select 'FAN_ENGAGEMENT', 'transactions', count(*) from {{ ref('stg_fan_transactions') }} where not is_refund
    union all
    -- every preference-centre opt-out follows an opt-in, so the number of such events is the number of opt-in then opt-out pairs
    select 'FAN_ENGAGEMENT', 'consent_pairs', count(*) from {{ ref('stg_fan_consent_events') }} where status = 'opt_out' and capture_point = 'preference_center'
    union all
    select 'INTL_FED', 'uk_rows', count(*) from {{ ref('stg_intl_registrations') }} where sheet_country_code = 'GB'
    union all
    select 'CA_CLUB', 'rows_with_consents_object', count(*)
    from {{ ref('stg_ca_registrations') }} where not list_contains(dq_flags, 'missing_consents_object')
    union all
    -- ZIPs that start with 0: those that kept it plus those that lost it (now 4 digits)
    select 'US_LEAGUE', 'zip_eligible_rows', count(*)
    from {{ ref('stg_us_registrations') }}
    where regexp_matches(trim(raw_postal), '^0\d{4}') or regexp_matches(trim(raw_postal), '^\d{4}$')

),

joined as (

    select
        coalesce(c.source_system, o.source_system)                          as source_system,
        coalesce(c.defect_id, o.defect_id)                                  as defect_id,
        c.kind,
        c.rule_description,
        c.detectable_phase1,
        c.denominator_description,
        c.configured_rate,
        c.configured_count,
        case when c.detectable_phase1 or c.defect_id is null then coalesce(o.observed_count, 0) end
                                                                            as observed_count,
        d.denominator                                                       as observed_denominator
    from {{ ref('dq_defect_config') }} c
    full outer join observed o
        on o.source_system = c.source_system and o.defect_id = c.defect_id
    left join denominators d
        on d.source_system = c.source_system and d.denominator_kind = c.denominator_kind

)

select
    source_system,
    defect_id,
    kind,
    detectable_phase1,
    denominator_description,
    configured_rate,
    configured_count,
    observed_count,
    observed_denominator,
    round(observed_count * 1.0 / nullif(observed_denominator, 0), 5)        as observed_rate,
    round((observed_count * 1.0 / nullif(observed_denominator, 0)) / nullif(configured_rate, 0), 3)
                                                                            as observed_to_configured_ratio,
    case
        when kind is null then 'NOT_CONFIGURED'
        when not detectable_phase1 then 'NOT_DETECTABLE_PHASE1'
        when kind = 'structural' and observed_count = configured_count then 'OK'
        when kind = 'zero' and observed_count = 0 then 'OK'
        when kind = 'rate' and abs(observed_count * 1.0 / observed_denominator / configured_rate - 1) <= {{ tolerance }} then 'OK'
        else 'OUT_OF_TOLERANCE'
    end                                                                     as status,
    rule_description
from joined
order by source_system, status, defect_id
