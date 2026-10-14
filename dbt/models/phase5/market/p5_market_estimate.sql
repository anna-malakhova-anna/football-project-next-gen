{{ config(schema='phase5') }}
-- depends_on: {{ ref('p5_params') }}
-- STEWARD view, all markets (including those with no club). The participation estimate per market for the latest season, with a band driven by data completeness.
-- NO RATE: a rate needs a population denominator and Phase 3 forbids inventing one (the synthetic stub was retired); see population_denominators and mart_market_coverage.
--   point      placed children + the allocated share of children with no usable ZIP
--   low        point minus the weakly identified children (no parent email and no birth year: school rosters, which no rule could match to another registration and which may all
--              duplicate a child already counted), scaled by the label-free LOW identity range (also merging PROBABLE links), times (1 - band_base).
--              This lower bound was ADDED after the first design missed the truth in 11 of 20 markets (ADR-012); its coverage below is therefore not an independent test.
--   high       point times (1 + band_base + band_k x missing), where missing = 1 - pass rate of the counting rules (band_rules): the less complete the market's data, the wider the band
-- This band is a rule of thumb that makes poor data look uncertain; it is NOT a statistical confidence interval (docs/market-estimate.md). A market with no children observed is NO_DATA, not zero.
with params as (

    select
        {{ p5_param('band_base') }}::double as band_base, {{ p5_param('band_k') }}::double as band_k,
        {{ p5_param('confidence_high') }}::double as conf_high, {{ p5_param('confidence_medium') }}::double as conf_medium,
        '{{ p5_param("band_rules") }}' as band_rules

),

w as (

    select cw.market_id,
           sum(weight) filter (where basis = 'PLACED') as placed_children,
           coalesce(sum(weight) filter (where basis like 'ALLOCATED%'), 0) as allocated_children,
           sum(weight) as point,
           coalesce(sum(weight) filter (where c.is_weakly_identified), 0) as weak_children
    from {{ ref('p5_child_market_weight') }} cw join {{ ref('p5_child') }} c using (p5_person_id)
    where cw.market_id <> 'UNALLOCATED'
    group by 1

),

identity as (

    -- among the children placed in a market: distinct LOW-range people / distinct point people
    select market_id, count(distinct low_person_id)::double / count(distinct p5_person_id) as low_ratio, count(distinct p5_person_id) as placed_n
    from {{ ref('p5_child') }} where market_id <> 'UNPLACED' group by 1

),

coverage as (

    select r.market_id, sum(r.n_pass)::double / nullif(sum(r.n_evaluated), 0) as counting_completeness
    from {{ ref('dq_rule_results_market') }} r, params p
    where list_contains(string_split(p.band_rules, '|'), r.rule_id)
    group by 1

),

club as (

    select market_id, count(*) as n_clubs, bool_or(role = 'SHARED') as is_shared from {{ ref('p5_club_territory') }} group by 1

),

est as (

    select
        m.market_id, m.market_name, m.region_code,
        coalesce(c.n_clubs, 0) as n_clubs, coalesce(c.is_shared, false) as is_shared,
        w.placed_children, w.allocated_children, w.point, w.weak_children,
        cv.counting_completeness,
        greatest(1 - cv.counting_completeness, 0) as missing,
        i.low_ratio,
        pr.band_base, pr.band_k, pr.conf_high, pr.conf_medium
    from {{ ref('market_map') }} m
    cross join params pr
    left join w on w.market_id = m.market_id
    left join identity i on i.market_id = m.market_id
    left join coverage cv on cv.market_id = m.market_id
    left join club c on c.market_id = m.market_id
    where m.country_code = 'US'

)

select
    market_id, market_name, region_code,
    case when n_clubs = 0 then 'NO_CLUB' when is_shared then 'SHARED' else 'PRIMARY' end as club_coverage,
    n_clubs,
    placed_children::integer                                                as placed_children,
    round(allocated_children, 1)                                            as allocated_children,
    round(weak_children, 1)                                                 as weakly_identified_children,
    round(point, 1)                                                         as estimate,
    round((point - weak_children) * coalesce(low_ratio, 1) * (1 - band_base), 1)              as estimate_low,
    round(point * (1 + band_base + band_k * missing), 1)                    as estimate_high,
    round(counting_completeness, 4)                                         as counting_completeness,
    case when point is null then 'NO_DATA'
         when (point * (1 + band_base + band_k * missing) - (point - weak_children) * coalesce(low_ratio, 1) * (1 - band_base)) / point <= conf_high then 'HIGH'
         when (point * (1 + band_base + band_k * missing) - (point - weak_children) * coalesce(low_ratio, 1) * (1 - band_base)) / point <= conf_medium then 'MEDIUM'
         else 'LOW' end                                                     as confidence,
    round((point * (1 + band_base + band_k * missing) - (point - weak_children) * coalesce(low_ratio, 1) * (1 - band_base)) / nullif(point, 0), 4) as relative_band_width
from est
