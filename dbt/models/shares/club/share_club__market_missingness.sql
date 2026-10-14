{{ config(tags=['phase5']) }}
-- CLUB share: girls' share of youth participants per club market and year, with the bounds that hold when the unknown-gender participants are all assigned either way (no imputation).
-- A market-year with fewer than k_min youth participants is suppressed whole. Counts are allocated (fractional); no segment below the market is published.
{% set k = privacy_param('k_min') %}
select
    club_market_id, participation_year,
    case when total >= {{ k }} then round(total, 1) end                     as youth_participants_in_cell,
    case when total >= {{ k }} then round(unknown, 1) end                   as unknown_gender_participants,
    case when total >= {{ k }} then value_known_only end                    as girls_share_known_only,
    case when total >= {{ k }} then bound_low end                           as girls_share_bound_low,
    case when total >= {{ k }} then bound_high end                          as girls_share_bound_high,
    case when total >= {{ k }} then missingness_verdict end                 as missingness_verdict,
    case when total >= {{ k }} then 'NONE' else 'PRIMARY' end               as suppressed
from {{ ref('mart_missingness_bias') }}
where kpi = 'girls_share_of_youth' and segment_value = 'ALL' and club_market_id <> 'ALL'
order by participation_year, club_market_id
