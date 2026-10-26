-- Minimum returns (Phase 7, ADR-030): one row per landed row, typed, with the market taken from the file name (minimum_return_<country>_<season>.csv)
-- and the template's checks re-run as flags, so a return that breaks its own arithmetic is visible here as well as in the contract results.
-- Aggregate-only: no individual, never resolved into participants (scripts/check_lineage.py). Empty in the published build.
select
    upper(regexp_extract(_source_file, 'minimum_return_([A-Za-z]{2})_', 1))  as country_code,
    try_cast(season as integer)                                              as season_year,
    trim(region)                                                             as region,
    trim(age_band)                                                           as age_band,
    try_cast(teams as integer)                                               as teams,
    try_cast(girls as integer)                                               as girls,
    try_cast(boys as integer)                                                as boys,
    try_cast(sex_not_recorded as integer)                                    as sex_not_recorded,
    try_cast(players as integer)                                             as players,
    try_cast(girls as integer) + try_cast(boys as integer) + try_cast(sex_not_recorded as integer) is distinct from try_cast(players as integer) as fails_total,
    try_cast(players as integer) < 5 * try_cast(teams as integer)           as fails_roster,
    trim(age_band) not in ('U8', 'U10', 'U12', 'U14', 'U17', 'ADULT')        as fails_age_band,
    _source_file, _row_number
from {{ source('raw', 'gmp_minimum_return') }}
