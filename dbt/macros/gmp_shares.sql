{#- Phase 7 (spec D10): DP6's exec ports are split by the legal regime assumed to apply (legal_regime.output_port), so each port can carry its own access
    policy. One macro per kind writes every regime's model, so the ports cannot drift apart; gmp_regime_ports_partition_the_markets checks that together
    they cover every program market exactly once. The regime on each row is an UNVERIFIED assumption until the privacy lead checks it. -#}

{% macro gmp_markets_share(port) -%}
-- EXEC share (DP6, ADR-025): status, counting grade, clubs with rights and the direction labels of the program markets in regime port '{{ port }}'.
-- No count of people; growth_pct is hidden when the like-for-like base is a small cell (fewer than k_min participants in the earlier season).
select
    s.country_code, s.country_name, s.region, s.legal_regime_id, r.regime_name, r.verification_status as regime_verification, s.status_on_page, s.season_year,
    s.status, s.status_reason, s.counting_grade, s.clubs_with_rights,
    d.participation_direction,
    case when d.participants_prev >= {{ privacy_param('k_min') }} then round(100 * d.growth, 1) end as growth_pct,
    round(100 * d.minimum_detectable_change, 1)                             as minimum_detectable_change_pct,
    d.proxy_direction, d.proxy_agreement, d.growth_rank
from {{ ref('mart_gmp_market_status') }} s
join {{ ref('mart_gmp_direction') }} d using (country_code)
join {{ ref('legal_regime') }} r using (legal_regime_id)
where s.output_port = '{{ port }}'
order by s.country_code
{%- endmacro %}

{% macro gmp_scenario_share(port) -%}
-- EXEC share (DP6, ADR-025 section 3): the PLANNING SCENARIO for markets with no participation source in regime port '{{ port }}'. Not a measurement:
-- every row carries scenario_label, and it is never shown beside or summed with measured values. Derived from DP3's published (suppressed) counts.
select
    s.country_code, s.country_name, s.region, s.legal_regime_id, r.regime_name, r.verification_status as regime_verification, s.status, s.season_year,
    s.clubs_with_rights, s.comparable_basis, s.comparable_markets, s.n_comparables, s.single_comparable,
    s.scenario_low, s.scenario_high, s.scenario_direction, s.scenario_label
from {{ ref('mart_gmp_scenario') }} s
join {{ ref('legal_regime') }} r using (legal_regime_id)
where s.output_port = '{{ port }}'
order by s.country_code
{%- endmacro %}

{% macro gmp_quality_trend_share(port) -%}
-- EXEC share (DP6, spec section 7): counting score and grade per season of the markets with a participation source in regime port '{{ port }}'.
-- Clubs appear only as counts. From DP4's dq_scorecard_country (COUNT purpose).
select
    q.country_code, m.country_name, m.legal_regime_id, q.season_year,
    q.score                                                                 as counting_score,
    q.grade                                                                 as counting_grade,
    q.limiting_dimension,
    q.known_orgs                                                            as clubs_known,
    q.reporting_orgs                                                        as clubs_filed
from {{ ref('dq_scorecard_country') }} q
join {{ ref('gmp_markets') }} m using (country_code)
join {{ ref('legal_regime') }} r using (legal_regime_id)
where q.purpose = 'COUNT' and q.dimension = 'PURPOSE_SCORE' and r.output_port = '{{ port }}'
order by q.country_code, q.season_year
{%- endmacro %}
