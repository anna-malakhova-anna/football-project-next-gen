{{ config(tags=['phase7']) }}
-- EXEC share (DP6, ADR-025): one row per Global Markets Program market: status, counting grade, clubs with rights, and the direction labels.
-- No count of people. growth_pct is hidden (NULL) when the market's like-for-like base is a small cell (fewer than k_min participants in the earlier
-- season). output_port names the regime port the row belongs to (an assumption about the applicable regime, legal_regime is unverified).
select
    s.country_code, s.country_name, s.region, s.legal_regime_id, s.output_port, s.status_on_page, s.season_year,
    s.status, s.status_reason, s.counting_grade, s.clubs_with_rights,
    d.participation_direction,
    case when d.participants_prev >= {{ privacy_param('k_min') }} then round(100 * d.growth, 1) end as growth_pct,
    round(100 * d.minimum_detectable_change, 1)                             as minimum_detectable_change_pct,
    d.proxy_direction, d.proxy_agreement, d.growth_rank
from {{ ref('mart_gmp_market_status') }} s
join {{ ref('mart_gmp_direction') }} d using (country_code)
order by s.country_code
