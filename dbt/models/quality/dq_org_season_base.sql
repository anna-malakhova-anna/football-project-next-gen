-- One row per KNOWN organization and season, reporting or not (rules at ORG_SEASON grain read this). The modelled sources come from the organization registry
-- (raw.org_registry: what the program knows, including organizations that sent no file); the Phase 5 channel feeds' organizations are the leagues of their catalog,
-- which reported a season when any record of it arrived. `reported` is the whole point: a dark organization has no rows in dq_record_base, so only this table can say so.
with seasons as (select distinct season_year from {{ ref('p5_record_quality') }}),

registry as (

    select org_id, source_system, org_name, region_code, channel, season_year::integer as season_year, reports_data = 'Y' as reported
    from {{ source('raw', 'org_registry') }}

),

channel_orgs as (

    select l.league_id as org_id, l.source_feed as source_system, l.league_name as org_name, l.state as region_code, 'CHANNEL_FEED' as channel, s.season_year,
           exists (select 1 from {{ ref('p5_record_quality') }} q where q.league_id = l.league_id and q.season_year = s.season_year) as reported
    from {{ source('raw_p5', 'p5_league_catalog') }} l cross join seasons s

),

unioned as (select * from registry union all select * from channel_orgs)

select
    u.*,
    (select count(*) from {{ ref('dq_record_base') }} b where b.org_id = u.org_id and b.season_year = u.season_year and b.source_system = u.source_system) as n_records
from unioned u
