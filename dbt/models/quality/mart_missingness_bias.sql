-- depends_on: {{ ref('observation_window') }}
-- Missingness is a finding, not a nuisance (phase-5-spec 6.2). For each participant-level KPI with a missing input, per year (and per segment), the value three ways and the evidence:
--   value_phase3        the Phase 3 figure: unknowns stay in the denominator (U is never imputed), so a girls' share is girls / all youth
--   value_known_only    the same KPI computed only where the field is known: girls / (girls + boys)
--   bound_low/high      Manski-style bounds with NO imputation: the KPI if every unknown fell into the extreme that lowers it, then the one that raises it
--   missing_share       unknowns / all
--   top_orgs, top_divisions   where the RECORD-level missingness concentrates (top three by count)
--   missingness_verdict  NOT_MISSING_AT_RANDOM when any factor in mart_missingness_tests is associated with the missing value; else NO_EVIDENCE_OF_PATTERN
-- KPIs: girls_share_of_youth (segments ALL and each youth division), age_band_mix (one row per age band). Geo attribution by club market is added at the market step.
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
miss_org as (

    select b.season_year as participation_year, 'girls_share_of_youth' as kpi, b.org_id as item, count(*) as n
    from {{ ref('dq_record_base') }} b where list_contains(b.dq_flags, 'missing_gender') and b.source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') group by all
    union all
    select b.season_year, 'age_band_mix', b.org_id, count(*) from {{ ref('dq_record_base') }} b
    where list_contains(b.dq_flags, 'dob_age_group_only') and b.source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') group by all

),

miss_div as (

    select u.season_year as participation_year, 'girls_share_of_youth' as kpi, coalesce(u.canonical_division, 'UNMAPPED') as item, count(*) as n
    from {{ ref('int_registrations_unioned') }} u where u.sex = 'U' and coalesce(u.is_minor, false) and not coalesce(u.is_exact_duplicate, false) group by all
    union all
    select u.season_year, 'age_band_mix', coalesce(u.canonical_division, 'UNMAPPED'), count(*) from {{ ref('int_registrations_unioned') }} u
    where u.birth_year is null and not coalesce(u.is_exact_duplicate, false) group by all

),

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

select
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
