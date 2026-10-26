-- Compares the CURRENT scorecard with the LATEST published snapshot of each year and lists every KPI whose value changed,
-- with old value, new value, delta and a likely cause (ADR-007):
--   DEFINITION_CHANGED  the methodology version differs AND the catalog says this KPI's definition changed in a version after the published one
--   METHODOLOGY_CHANGE  the methodology version differs (the definition did not change; the value moved under the new version)
--   NEW_KPI             the KPI did not exist in the published snapshot of that year (an addition, never a restatement)
--   SOURCE_REGISTRY_CHANGE  a KPI counted from the source registry alone (sources known, sources onboarded) moved: a source was added or changed status
--   NEW_SOURCE_DATA     the raw row counts of the sources differ (new or late files)
--   IDENTITY_CHANGE     the registration -> participant assignment differs (new links, a steward decision, a new run)
--   UNKNOWN             none of the above explains it
-- restatement_required applies the ADR-007 threshold to HEADLINE KPIs: a relative change above 1% (an absolute change of a
-- percentage point for rates) or any methodology change or definition change. A NEW_KPI is listed (so the addition is visible) but never restates. Data-trust KPIs (open review items and so on) move legitimately and
-- are listed but never require a restatement. An empty log means nothing published has changed.
with latest as (

    select participation_year, kpi_id, value, snapshot_id, published_at, methodology_version, raw_rows_us, raw_rows_ca,
           raw_rows_intl, identity_fingerprint
    from {{ source('published', 'scorecard_snapshots') }}
    qualify row_number() over (partition by participation_year, kpi_id order by published_at desc, snapshot_id desc) = 1

),

now_ctx as (

    select
        (select count(*) from {{ source('raw', 'us_league_registrations') }})     as raw_rows_us,
        (select count(*) from {{ source('raw', 'ca_club_records') }})             as raw_rows_ca,
        (select count(*) from {{ source('raw', 'intl_federation_returns') }})     as raw_rows_intl,
        (select md5(string_agg(registration_key || participant_id, '|' order by registration_key))
           from {{ ref('bridge_registration_participant') }})                     as identity_fingerprint

),

changed_values as (

    select
        c.participation_year,
        c.kpi_id,
        c.kpi_group,
        m.unit,
        l.value                                                             as old_value,
        c.value                                                             as new_value,
        c.value - l.value                                                   as delta,
        round((c.value - l.value) / nullif(abs(l.value), 0), 6)             as pct_change,
        l.snapshot_id,
        l.published_at,
        l.methodology_version                                               as old_methodology_version,
        c.methodology_version                                               as new_methodology_version,
        case
            when l.methodology_version <> c.methodology_version
                 and m.definition_changed_in <> ''
                 and {{ version_num('m.definition_changed_in') }} > {{ version_num('l.methodology_version') }}
                 and {{ version_num('m.definition_changed_in') }} <= {{ version_num('c.methodology_version') }} then 'DEFINITION_CHANGED'
            when l.methodology_version <> c.methodology_version then 'METHODOLOGY_CHANGE'
            when c.kpi_id in ('sources_known', 'sources_onboarded') then 'SOURCE_REGISTRY_CHANGE'   -- counted from source_registry and nothing else
            when (l.raw_rows_us, l.raw_rows_ca, l.raw_rows_intl) <> (n.raw_rows_us, n.raw_rows_ca, n.raw_rows_intl) then 'NEW_SOURCE_DATA'
            when l.identity_fingerprint <> n.identity_fingerprint then 'IDENTITY_CHANGE'
            else 'UNKNOWN'
        end                                                                 as likely_cause
    from {{ ref('mart_kpi_scorecard') }} c
    join latest l on l.participation_year = c.participation_year and l.kpi_id = c.kpi_id
    join {{ ref('metric_catalog') }} m on m.metric_id = c.kpi_id
    cross join now_ctx n
    where c.value is distinct from l.value and abs(coalesce(c.value, 0) - coalesce(l.value, 0)) > 1e-9

),

published_years as (select distinct participation_year, methodology_version from latest),

new_kpis as (

    select
        c.participation_year, c.kpi_id, c.kpi_group, m.unit,
        cast(null as double) as old_value, c.value as new_value, cast(null as double) as delta, cast(null as double) as pct_change,
        cast(null as varchar) as snapshot_id, cast(null as timestamp) as published_at,
        y.methodology_version as old_methodology_version, c.methodology_version as new_methodology_version,
        'NEW_KPI' as likely_cause
    from {{ ref('mart_kpi_scorecard') }} c
    join published_years y on y.participation_year = c.participation_year
    join {{ ref('metric_catalog') }} m on m.metric_id = c.kpi_id
    where not exists (select 1 from latest l where l.participation_year = c.participation_year and l.kpi_id = c.kpi_id)

),

changed as (select * from changed_values union all by name select * from new_kpis)

select
    *,
    kpi_group in ('north_star', 'growth', 'reach', 'depth')                 as is_headline_kpi,
    kpi_group in ('north_star', 'growth', 'reach', 'depth')
        and likely_cause <> 'NEW_KPI'
        and (likely_cause in ('METHODOLOGY_CHANGE', 'DEFINITION_CHANGED')
             or (unit = 'rate' and abs(delta) > 0.01)
             or (unit <> 'rate' and abs(coalesce(pct_change, 1)) > 0.01)) as restatement_required
from changed
order by participation_year, kpi_id
