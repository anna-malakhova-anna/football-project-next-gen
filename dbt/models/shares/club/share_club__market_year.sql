{{ config(tags=['phase5']) }}
-- CLUB share: one row per club market (a project approximation, ADR-016) and year, plus a year total (club_market_id NULL). AGGREGATE ONLY: allocated participants (fractional, because a ZIP3 shared by
-- several markets is split by weight), the coverage estimate with its interval, and the purpose grades. Primary AND secondary suppression through suppress_small_cells; when a market-year is suppressed, every
-- column derived from the same records (interval, geo fitness, grades, rate) is hidden with it, so a grade is never published for a market too small to publish a count for.
-- No participant, household or record key; no organization id; nothing from the restricted `linkage` schema is selected (only approved aggregate marts are read).
with m as (

    select club_market_id, market_name, participation_year, participants_allocated, youth_participants_allocated, orgs_known, orgs_reporting, orgs_dark,
           coverage_point as participants_not_reported_estimate, interval_low as participants_allocated_interval_low, interval_high as participants_allocated_interval_high,
           pct_records_geo_fit, grade_count, grade_segment, grade_geo, grade_retain, grade_activate, denominator_status, participation_rate
    from {{ ref('mart_market_coverage') }}

),

src as (

    select club_market_id, market_name, participation_year, participants_allocated, youth_participants_allocated, orgs_known, orgs_reporting, orgs_dark,
           participants_not_reported_estimate, participants_allocated_interval_low, participants_allocated_interval_high, pct_records_geo_fit,
           grade_count, grade_segment, grade_geo, grade_retain, grade_activate, denominator_status, participation_rate
    from m
    union all
    select cast(null as varchar), 'All club markets', participation_year, sum(participants_allocated), sum(youth_participants_allocated), sum(orgs_known), sum(orgs_reporting), sum(orgs_dark),
           sum(participants_not_reported_estimate), cast(null as double), cast(null as double), cast(null as double),
           cast(null as varchar), cast(null as varchar), cast(null as varchar), cast(null as varchar), cast(null as varchar), cast(null as varchar), cast(null as double)
    from m group by participation_year

),

s as (

    select club_market_id, market_name, participation_year, participants_allocated, youth_participants_allocated, orgs_known, orgs_reporting, orgs_dark, participants_not_reported_estimate,
           participants_allocated_interval_low, participants_allocated_interval_high, pct_records_geo_fit, grade_count, grade_segment, grade_geo, grade_retain, grade_activate, denominator_status, participation_rate, suppressed
    from {{ suppress_small_cells('src', ['participation_year', 'club_market_id'], ['participants_allocated', 'youth_participants_allocated'], secondary_col='participants_allocated',
        passthrough=['market_name', 'orgs_known', 'orgs_reporting', 'orgs_dark', 'participants_not_reported_estimate', 'participants_allocated_interval_low', 'participants_allocated_interval_high',
                     'pct_records_geo_fit', 'grade_count', 'grade_segment', 'grade_geo', 'grade_retain', 'grade_activate', 'denominator_status', 'participation_rate']) }}

)

select
    club_market_id, market_name, participation_year,
    round(participants_allocated, 1)                                        as participants_allocated,
    round(youth_participants_allocated, 1)                                  as youth_participants_allocated,
    case when suppressed = 'NONE' then orgs_known end                       as orgs_known,
    case when suppressed = 'NONE' then orgs_reporting end                   as orgs_reporting,
    case when suppressed = 'NONE' then orgs_dark end                        as orgs_dark,
    case when suppressed = 'NONE' then round(participants_not_reported_estimate, 1) end as participants_not_reported_estimate,
    case when suppressed = 'NONE' then round(participants_allocated_interval_low, 1) end  as participants_allocated_interval_low,
    case when suppressed = 'NONE' then round(participants_allocated_interval_high, 1) end as participants_allocated_interval_high,
    case when suppressed = 'NONE' then pct_records_geo_fit end              as pct_records_geo_fit,
    case when suppressed = 'NONE' then grade_count end                      as grade_count,
    case when suppressed = 'NONE' then grade_segment end                    as grade_segment,
    case when suppressed = 'NONE' then grade_geo end                        as grade_geo,
    case when suppressed = 'NONE' then grade_retain end                     as grade_retain,
    case when suppressed = 'NONE' then grade_activate end                   as grade_activate,
    denominator_status,
    case when suppressed = 'NONE' then participation_rate end               as participation_rate,
    suppressed
from s
order by participation_year, club_market_id nulls first
