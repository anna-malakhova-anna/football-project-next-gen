{{ config(tags=['phase7']) }}
-- GROUND TRUTH (evaluation only, synthetic; ADR-025 section 6). Per market with no participation source: did the planning scenario's range contain the
-- true latest-season participants, did its direction match the true direction, and did the club proxy's direction match it? Graded here, never fed back.
-- The answer key's directions were set against the comparables in a configured share of markets: an ASSUMPTION, so the result shows what the scenario
-- would get wrong IF markets behave that way, not evidence about real markets. The generator picks comparables from the markets with data, dbt from the
-- MEASURED markets; where the two differ, comparables_differ says so.
with truth as (

    select t.* from {{ source('ground_truth', 'gmp_market_truth') }} t
    where t.season_year = (select max(season_year) from {{ source('ground_truth', 'gmp_market_truth') }})

)

select
    s.country_code, s.status, s.season_year, s.comparable_basis, s.comparable_markets,
    t.comparable_markets                                                    as generator_comparable_markets,
    s.comparable_markets is distinct from t.comparable_markets              as comparables_differ,
    s.scenario_low, s.scenario_high,
    t.true_participants,
    t.true_participants between s.scenario_low and s.scenario_high          as truth_in_range,
    case when t.true_participants < s.scenario_low then 'BELOW' when t.true_participants > s.scenario_high then 'ABOVE' else 'INSIDE' end as truth_vs_range,
    s.scenario_direction,
    t.true_direction,
    s.scenario_direction = t.true_direction                                 as direction_match,
    d.proxy_direction,
    case when d.proxy_direction in ('GROWING', 'SHRINKING', 'FLAT') then d.proxy_direction = t.true_direction end as proxy_match,
    t.set_against_comparables
from {{ ref('mart_gmp_scenario') }} s
join truth t using (country_code)
left join {{ ref('mart_gmp_direction') }} d using (country_code)
order by s.country_code
