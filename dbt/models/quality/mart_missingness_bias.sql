-- depends_on: {{ ref('observation_window') }}
-- Missingness is a finding, not a nuisance (phase-5-spec 6.2). For each participant-level KPI with a missing input, per year (and per segment), the value three ways and the evidence:
--   value_phase3        the Phase 3 figure: unknowns stay in the denominator (U is never imputed), so a girls' share is girls / all youth
--   value_known_only    the same KPI computed only where the field is known: girls / (girls + boys)
--   bound_low/high      Manski-style bounds with NO imputation: the KPI if every unknown fell into the extreme that lowers it, then the one that raises it
--   missing_share       unknowns / all
--   top_orgs, top_divisions   where the RECORD-level missingness concentrates (top three by count)
--   missingness_verdict  NOT_MISSING_AT_RANDOM when any factor in mart_missingness_tests is associated with the missing value; else NO_EVIDENCE_OF_PATTERN
-- KPIs: girls_share_of_youth (segments ALL and each youth division), age_band_mix (one row per age band), and the CLUB-MARKET SLICES (club_market_id <> 'ALL'): the girls' share of youth in each club market
-- (allocated counts) and club_market_attribution, the share of US participants that fall in the market, where US participants with no usable ZIP are the unknowns (bounds: all of them elsewhere, or all of
-- them here). A club market is a project approximation (club_market_map).
with py as (select * from {{ ref('fct_participant_year') }}),

girls as (

    select participation_year, coalesce(primary_division, 'UNKNOWN') as segment_value,
           count(*) filter (where sex = 'F') as girls, count(*) filter (where sex = 'M') as boys, count(*) filter (where sex = 'U') as unknown
    from py where is_youth group by rollup (participation_year, primary_division) having participation_year is not null

),

girls_rows as (

    select participation_year, 'girls_share_of_youth' as kpi,
           case when segment_value = 'UNKNOWN' and not exists (select 1 from py x where x.participation_year = g.participation_year and x.primary_division is null and x.is_youth) then 'ALL' else segment_value end as segment_value,
           girls as numerator_known, (girls + boys + unknown) as total, unknown,
           girls::double / nullif(girls + boys + unknown, 0)               as value_phase3,
           girls::double / nullif(girls + boys, 0)                         as value_known_only,
           girls::double / nullif(girls + boys + unknown, 0)               as bound_low,
           (girls + unknown)::double / nullif(girls + boys + unknown, 0)   as bound_high
    from girls g

),

age as (

    select participation_year, age_band as segment_value, count(*) as n,
           count(*) filter (where age_band = 'UNKNOWN') over (partition by participation_year) as unknown, sum(count(*)) over (partition by participation_year) as total
    from py group by participation_year, age_band

),

age_rows as (

    select participation_year, 'age_band_mix' as kpi, segment_value, n as numerator_known, total, unknown::bigint as unknown,
           n::double / total as value_phase3,
           case when segment_value = 'UNKNOWN' then null else n::double / (total - unknown) end as value_known_only,
           case when segment_value = 'UNKNOWN' then null else n::double / total end as bound_low,
           case when segment_value = 'UNKNOWN' then null else (n + unknown)::double / total end as bound_high
    from age

),

rows as (select * from girls_rows where segment_value <> 'UNKNOWN' or kpi = 'girls_share_of_youth' union all select * from age_rows),

-- where the missing records concentrate
-- where the missing records concentrate (DP1 aggregate port dq_missing_concentration)
miss_org as (select participation_year, kpi, item, n from {{ ref('dq_missing_concentration') }} where item_type = 'ORGANIZATION'),

miss_div as (select participation_year, kpi, item, n from {{ ref('dq_missing_concentration') }} where item_type = 'DIVISION'),

top_orgs as (

    select participation_year, kpi, string_agg(item || ' (' || n || ')', '; ' order by n desc) filter (where rn <= 3) as top_orgs
    from (select *, row_number() over (partition by participation_year, kpi order by n desc, item) as rn from miss_org) group by 1, 2

),

top_divs as (

    select participation_year, kpi, string_agg(item || ' (' || n || ')', '; ' order by n desc) filter (where rn <= 3) as top_divisions
    from (select *, row_number() over (partition by participation_year, kpi order by n desc, item) as rn from miss_div) group by 1, 2

),

verdict as (

    select participation_year, kpi, bool_or(associated_with_missingness) as any_pattern,
           string_agg(factor, ', ' order by factor) filter (where associated_with_missingness) as factors
    from {{ ref('mart_missingness_tests') }} group by 1, 2

)

,
national as (

select
    'ALL' as club_market_id,
    r.participation_year, r.kpi, r.segment_value,
    r.numerator_known, r.total, r.unknown,
    round(r.value_phase3, 4)                                                as value_phase3,
    round(r.value_known_only, 4)                                            as value_known_only,
    round(r.bound_low, 4)                                                   as bound_low,
    round(r.bound_high, 4)                                                  as bound_high,
    round(r.unknown::double / nullif(r.total, 0), 4)                        as missing_share,
    o.top_orgs, d.top_divisions,
    case when v.any_pattern then 'NOT_MISSING_AT_RANDOM' else 'NO_EVIDENCE_OF_PATTERN' end as missingness_verdict,
    v.factors                                                               as associated_factors
from rows r
left join top_orgs o using (participation_year, kpi)
left join top_divs d using (participation_year, kpi)
left join verdict v using (participation_year, kpi)

),

mw as (

    select w.participation_year, w.club_market_id, w.basis, w.weight, py.is_youth, py.sex, py.attributed_country_code
    from {{ ref('int_participant_year_market') }} w join {{ ref('fct_participant_year') }} py using (participant_id, participation_year)

),

market_girls as (

    select club_market_id, participation_year, 'girls_share_of_youth' as kpi, 'ALL' as segment_value,
           sum(weight) filter (where sex = 'F') as girls, sum(weight) filter (where sex = 'M') as boys, sum(weight) filter (where sex = 'U') as unk
    from mw where is_youth and club_market_id not in ('UNALLOCATED') group by all

),

market_attr as (

    select participation_year,
           sum(weight) filter (where basis = 'ZIP3') as placed_all, sum(weight) as us_all, sum(weight) filter (where basis <> 'ZIP3') as unplaced_all
    from mw where attributed_country_code = 'US' group by all

),

market_rows as (

    select g.club_market_id, g.participation_year, g.kpi, g.segment_value,
           round(g.girls, 1) as numerator_known, round(coalesce(g.girls, 0) + coalesce(g.boys, 0) + coalesce(g.unk, 0), 1) as total, round(coalesce(g.unk, 0), 1) as unknown,
           round(g.girls / nullif(g.girls + g.boys + g.unk, 0), 4) as value_phase3, round(g.girls / nullif(g.girls + g.boys, 0), 4) as value_known_only,
           round(g.girls / nullif(g.girls + g.boys + g.unk, 0), 4) as bound_low, round((g.girls + g.unk) / nullif(g.girls + g.boys + g.unk, 0), 4) as bound_high,
           round(g.unk / nullif(g.girls + g.boys + g.unk, 0), 4) as missing_share
    from market_girls g
    union all
    select m.club_market_id, m.participation_year, 'club_market_attribution', 'ALL',
           round(sum(m.weight) filter (where m.basis = 'ZIP3'), 1), round(a.us_all, 1), round(a.unplaced_all, 1),
           round(sum(m.weight) / a.us_all, 4), round(sum(m.weight) filter (where m.basis = 'ZIP3') / a.placed_all, 4),
           round(sum(m.weight) filter (where m.basis = 'ZIP3') / a.us_all, 4), round((sum(m.weight) filter (where m.basis = 'ZIP3') + a.unplaced_all) / a.us_all, 4), round(a.unplaced_all / a.us_all, 4)
    from mw m join market_attr a using (participation_year)
    where m.attributed_country_code = 'US' and m.club_market_id not in ('UNALLOCATED', 'NO_CLUB_MARKET') group by m.club_market_id, m.participation_year, a.us_all, a.placed_all, a.unplaced_all

)

select * from national
union all
select club_market_id, participation_year, kpi, segment_value, numerator_known, total, unknown, value_phase3, value_known_only, bound_low, bound_high, missing_share,
       cast(null as varchar), cast(null as varchar), cast(null as varchar), cast(null as varchar)
from market_rows
