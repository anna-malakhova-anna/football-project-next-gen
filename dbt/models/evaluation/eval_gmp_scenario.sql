{{ config(tags=['phase7']) }}
-- GROUND TRUTH (evaluation only, synthetic; ADR-025 section 6). Per market with no participation source: did the planning scenario's range contain the
-- true latest-season participants, did its direction match the true direction, and did the club proxy's direction match it? Graded here, never fed back.
-- The answer key's directions were set against the comparables in a configured share of markets: an ASSUMPTION, so the result shows what the scenario
-- would get wrong IF markets behave that way, not evidence about real markets. The generator picks comparables from the markets with data, dbt from the
-- MEASURED markets; where the two differ, comparables_differ says so.
-- Direction is graded only where the true move is larger than the minimum detectable change the scenario's direction rests on (ADR-045, option A
-- of ADR-039): a smaller move is one the method never claimed it could see, so direction_match is NULL there (not gradable), not FALSE.
with truth as (

    select t.* from {{ source('ground_truth', 'gmp_market_truth') }} t
    where t.season_year = (select max(season_year) from {{ source('ground_truth', 'gmp_market_truth') }})

),

-- one pooled value for every market (ADR-025 section 6)
floor_ as (select max(minimum_detectable_change) as minimum_detectable_change from {{ ref('mart_gmp_direction') }})

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
    t.true_growth,
    f.minimum_detectable_change,
    abs(t.true_growth) > f.minimum_detectable_change                        as direction_gradable,
    case when abs(t.true_growth) > f.minimum_detectable_change
         then s.scenario_direction = t.true_direction end                   as direction_match,
    d.proxy_direction,
    case when d.proxy_direction in ('GROWING', 'SHRINKING', 'FLAT') then d.proxy_direction = t.true_direction end as proxy_match,
    t.set_against_comparables
from {{ ref('mart_gmp_scenario') }} s
join truth t using (country_code)
left join {{ ref('mart_gmp_direction') }} d using (country_code)
cross join floor_ f
order by s.country_code
