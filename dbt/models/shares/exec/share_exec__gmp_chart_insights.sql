{{ config(tags=['phase7']) }}
-- EXEC share (DP6, Phase 7 step 9): the numbers inside the headline sentences of the Global outlook cards (G0, G1, G2, G4, G5), in the long shape of the other
-- chart-insight shares. Every value is rounded and worded here, never in the browser. G3's numbers read the answer key, so they live in eval_chart_insights.
with m as (
    select country_code, country_name, status, participation_direction, minimum_detectable_change_pct, season_year from {{ ref('share_exec__gmp_markets_eu_uk') }}
    union all select country_code, country_name, status, participation_direction, minimum_detectable_change_pct, season_year from {{ ref('share_exec__gmp_markets_canada') }}
    union all select country_code, country_name, status, participation_direction, minimum_detectable_change_pct, season_year from {{ ref('share_exec__gmp_markets_other') }}
),

counts as (
    select count(*) as n_markets,
           count(*) filter (where status = 'MEASURED') as n_measured, count(*) filter (where status = 'PARTIAL') as n_partial,
           count(*) filter (where status = 'PROXY_ONLY') as n_proxy_only, count(*) filter (where status = 'DARK') as n_dark,
           count(*) filter (where participation_direction in ('GROWING', 'SHRINKING')) as n_moving,
           max(minimum_detectable_change_pct) as mdc_pct
    from m
),

trend as (
    select country_code, country_name, season_year, clubs_known, clubs_filed from {{ ref('share_exec__gmp_quality_trend_eu_uk') }}
    union all select country_code, country_name, season_year, clubs_known, clubs_filed from {{ ref('share_exec__gmp_quality_trend_canada') }}
    union all select country_code, country_name, season_year, clubs_known, clubs_filed from {{ ref('share_exec__gmp_quality_trend_other') }}
),

-- markets below the Measured band in the latest season, and how many more clubs would have to file to reach it (timeliness = clubs filed / known)
close as (
    select t.country_name, greatest(0, ceil(b.min_score / 100.0 * t.clubs_known)::integer - t.clubs_filed) as clubs_needed
    from trend t
    join m on m.country_code = t.country_code and m.status = 'PARTIAL' and m.season_year = t.season_year
    cross join (select min_score from {{ ref('dq_grade_bands') }} where grade = (select value from {{ ref('p7_params') }} where param = 'measured_min_grade')) b
),

one_club as (
    select count(*) as n_close, max(clubs_needed) as max_clubs_needed,
           string_agg(case country_name when 'United Kingdom' then 'the UK' else country_name end, ' and ' order by country_name) as close_markets
    from close
),

continents as (
    select count(distinct continent) as n_continents from {{ ref('gmp_map_points') }}
),

now_lane as (
    select count(*) as n_now from {{ ref('share_exec__gmp_board') }} where lane = 'NOW'
),

rows_ as (
    select 'G0' as chart_id, 'both' as lens, 'n_markets' as field, cast(n_markets as varchar) as value_display, n_markets * 1.0 as value_raw from counts
    union all select 'G0', 'both', 'n_continents', cast(n_continents as varchar), n_continents * 1.0 from continents
    union all select 'G1', 'both', 'n_markets', cast(n_markets as varchar), n_markets * 1.0 from counts
    union all select 'G1', 'both', 'n_readable', cast(n_measured + n_partial as varchar), (n_measured + n_partial) * 1.0 from counts
    union all select 'G1', 'both', 'n_measured', cast(n_measured as varchar), n_measured * 1.0 from counts
    union all select 'G1', 'both', 'n_partial', cast(n_partial as varchar), n_partial * 1.0 from counts
    union all select 'G1', 'both', 'n_proxy_only', cast(n_proxy_only as varchar), n_proxy_only * 1.0 from counts
    union all select 'G1', 'both', 'n_dark', cast(n_dark as varchar), n_dark * 1.0 from counts
    union all select 'G2', 'both', 'mdc_pct', cast(round(mdc_pct) as bigint) || '%', mdc_pct from counts
    union all select 'G2', 'both', 'n_moving', cast(n_moving as varchar), n_moving * 1.0 from counts
    union all select 'G2', 'both', 'n_with_data', cast(n_measured + n_partial as varchar), (n_measured + n_partial) * 1.0 from counts
    union all select 'G4', 'both', 'n_close', cast(n_close as varchar), n_close * 1.0 from one_club
    union all select 'G4', 'both', 'close_markets', close_markets, null from one_club
    union all select 'G4', 'both', 'clubs_needed_text', case max_clubs_needed when 1 then 'one more club' else cast(max_clubs_needed as varchar) || ' more clubs' end, max_clubs_needed * 1.0 from one_club
    union all select 'G5', 'both', 'n_now', cast(n_now as varchar), n_now * 1.0 from now_lane
)

select chart_id, lens, field, value_display, value_raw, 'NONE' as suppressed from rows_ order by chart_id, field
