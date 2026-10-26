{{ config(tags=['phase7']) }}
-- EXEC share (DP6, ADR-025 section 3): the PLANNING SCENARIO for markets with no participation source. Not a measurement: every row carries
-- scenario_label, and the site shows it in its own section, never beside or summed with measured values. The range is derived from DP3's published
-- (already suppressed) country counts and the clubs with rights; it names no person and no organization.
select
    country_code, country_name, region, output_port, status, season_year, clubs_with_rights,
    comparable_basis, comparable_markets, n_comparables, single_comparable,
    scenario_low, scenario_high, scenario_direction, scenario_label
from {{ ref('mart_gmp_scenario') }}
order by country_code
