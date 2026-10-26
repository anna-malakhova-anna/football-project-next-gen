-- GMP_PROXY staging (Phase 7, ADR-025): one row per landed club return, typed, with the market resolved to its country code. Aggregate-only:
-- no individual, and never participation (scripts/check_lineage.py keeps it apart from every participant model).
--   is_superseded  a market-season filed by two clubs keeps the LATEST report_date (ties: the lower club id); the other row is superseded, not dropped
--   events_known   club_events was filled in (a blank is unknown, never zero)
--   has_signal     the return shows any sign of flag football activity: events above zero, a game, or a national federation
with typed as (

    select
        m.country_code,
        trim(r.market)                                                       as market_as_filed,
        try_cast(r.season as integer)                                        as season_year,
        try_cast(nullif(trim(r.club_events), '') as integer)                 as club_events,
        try_cast(r.games_in_market as integer)                               as games_in_market,
        case trim(r.federation_exists) when 'Y' then true when 'N' then false end as federation_exists,
        trim(r.reported_by)                                                  as reported_by,
        try_cast(r.report_date as date)                                      as report_date,
        r._source_file, r._row_number
    from {{ source('raw', 'gmp_proxy') }} r
    left join {{ ref('gmp_markets') }} m on m.country_name = trim(r.market)

)

select
    *,
    club_events is not null                                                  as events_known,
    coalesce(club_events, 0) > 0 or coalesce(games_in_market, 0) > 0 or coalesce(federation_exists, false) as has_signal,
    row_number() over (partition by country_code, season_year order by report_date desc, reported_by) > 1 as is_superseded
from typed
