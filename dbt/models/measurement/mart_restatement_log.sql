-- Compares the CURRENT scorecard with the LATEST published snapshot of each year and lists every KPI whose value changed,
-- with old value, new value, delta and a likely cause (ADR-007):
--   METHODOLOGY_CHANGE  the methodology version differs
--   NEW_SOURCE_DATA     the raw row counts of the sources differ (new or late files)
--   IDENTITY_CHANGE     the registration -> participant assignment differs (new links, a steward decision, a new run)
--   UNKNOWN             none of the above explains it
-- restatement_required applies the ADR-007 threshold to HEADLINE KPIs: a relative change above 1% (an absolute change of a
-- percentage point for rates) or any methodology change. Data-trust KPIs (open review items and so on) move legitimately and
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

changed as (

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
            when l.methodology_version <> c.methodology_version then 'METHODOLOGY_CHANGE'
            when (l.raw_rows_us, l.raw_rows_ca, l.raw_rows_intl) <> (n.raw_rows_us, n.raw_rows_ca, n.raw_rows_intl) then 'NEW_SOURCE_DATA'
            when l.identity_fingerprint <> n.identity_fingerprint then 'IDENTITY_CHANGE'
            else 'UNKNOWN'
        end                                                                 as likely_cause
    from {{ ref('mart_kpi_scorecard') }} c
    join latest l on l.participation_year = c.participation_year and l.kpi_id = c.kpi_id
    join {{ ref('metric_catalog') }} m on m.metric_id = c.kpi_id
    cross join now_ctx n
    where c.value is distinct from l.value and abs(coalesce(c.value, 0) - coalesce(l.value, 0)) > 1e-9

)

select
    *,
    kpi_group in ('north_star', 'growth', 'reach', 'depth')                 as is_headline_kpi,
    kpi_group in ('north_star', 'growth', 'reach', 'depth')
        and (likely_cause = 'METHODOLOGY_CHANGE'
             or (unit = 'rate' and abs(delta) > 0.01)
             or (unit <> 'rate' and abs(coalesce(pct_change, 1)) > 0.01)) as restatement_required
from changed
order by participation_year, kpi_id
