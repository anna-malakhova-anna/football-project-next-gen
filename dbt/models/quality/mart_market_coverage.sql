-- depends_on: {{ ref('population_denominators') }}
-- How much of a club market does the data cover, and how far can it be trusted? One row per club market and participation year (phase-5-spec 9.2). The market is a PROJECT APPROXIMATION
-- (club_market_map: contiguous ZIP3 groups, shared markets split equally by default), not any club's territory. Counts are ALLOCATED, so they are fractional where a ZIP3 is shared.
--   participants_zip_placed / _unplaced_allocated / _outside_us   split by how the participants were placed (int_participant_year_market): a US participant with no usable ZIP is allocated by where
--                                                                 their organization's (else state's) placed participants live, reported SEPARATELY and never merged into the placed count
--   participants_allocated, youth_participants_allocated          the totals (youth = age 17 or under at the cutoff)
--   orgs_known / orgs_reporting / orgs_dark                       known organizations (organization registry; each organization belongs to the one market with the highest weight for its ZIP3) and how many sent a file
--   coverage_*                                                    participants of dark organizations, estimated from reporting peers (int_dark_org_coverage), spread the same way: an estimate with an interval
--   interval_low / interval_high                                  allocated participants + coverage low / high: the participant scale of the COVERAGE bar
--   pct_records_geo_fit                                           the allocated share of the market's records that are fit for the GEO purpose
--   grade_<purpose>                                               the market's purpose grades (dq_scorecard_market), on the Wilson lower bound where the sample is small
--   participation rate    ONLY if population_denominators has rows for the market's ZIP3: youth participants allocated / youth population, labelled "illustrative only: synthetic participant counts
--                         over real population denominators" (Phase 3). Otherwise denominator_status says "denominator not loaded" and the rate is NULL: no figure is invented.
with w as (select * from {{ ref('int_participant_year_market') }}),

py as (select participant_id, participation_year, is_youth from {{ ref('fct_participant_year') }}),

people as (

    select w.club_market_id, w.participation_year,
           sum(w.weight) as participants_allocated,
           sum(w.weight) filter (where w.basis = 'ZIP3') as participants_zip_placed,
           sum(w.weight) filter (where w.basis like 'UNPLACED_ALLOCATED%') as participants_unplaced_allocated,
           sum(w.weight) filter (where w.basis = 'OUTSIDE_US') as participants_outside_us,
           sum(w.weight) filter (where py.is_youth) as youth_participants_allocated
    from w join py using (participant_id, participation_year) group by all

),

primary_market as (

    -- an organization is a whole thing: it belongs to ONE market, the one with the highest weight for its ZIP3 (ties: the lowest market id). Participants are still split by weight; organizations never are (Phase 5.1, ADR-020).
    select zip3, club_market_id, 1.0 as weight
    from (select zip3, club_market_id, row_number() over (partition by zip3 order by allocation_weight desc, club_market_id) as rn from {{ ref('club_market_map') }})
    where rn = 1

),

org_w as (

    select o.source_system, o.org_id, o.season_year, o.reported, m.club_market_id, m.weight
    from {{ ref('dq_org_season_base') }} o
    join primary_market m on m.zip3 = o.zip3 and o.source_system = 'US_LEAGUE'
    where o.source_system = 'US_LEAGUE'
    union all
    select o.source_system, o.org_id, o.season_year, o.reported, 'OUTSIDE_US', 1.0 from {{ ref('dq_org_season_base') }} o where o.source_system in ('CA_CLUB', 'INTL_FED')

),

orgs as (

    select club_market_id, season_year as participation_year, sum(weight) as orgs_known, sum(weight) filter (where reported) as orgs_reporting, sum(weight) filter (where not reported) as orgs_dark
    from org_w group by all

),

cov as (

    select m.club_market_id, d.season_year as participation_year,
           sum(m.weight * d.q25) as coverage_low, sum(m.weight * d.q50) as coverage_point, sum(m.weight * d.q75) as coverage_high
    from {{ ref('int_dark_org_coverage') }} d
    join (select zip3, club_market_id, allocation_weight as weight from {{ ref('club_market_map') }}
          union all select cast(null as varchar), 'OUTSIDE_US', 1.0) m on (m.zip3 = d.zip3 and d.source_system = 'US_LEAGUE') or (m.club_market_id = 'OUTSIDE_US' and d.source_system in ('CA_CLUB', 'INTL_FED'))
    group by all

),

geo as (

    select m.club_market_id, f.participation_year, sum(m.weight * f.records_fit_for_geo) / nullif(sum(m.weight * f.records), 0) as pct_records_geo_fit
    from {{ ref('dq_geo_fit_person_year') }} f join w m on m.participant_id = f.participant_id and m.participation_year = f.participation_year
    group by all

),

grades as (

    select club_market_id, season_year as participation_year,
           max(grade) filter (where purpose = 'COUNT') as grade_count, max(grade) filter (where purpose = 'SEGMENT') as grade_segment, max(grade) filter (where purpose = 'GEO') as grade_geo,
           max(grade) filter (where purpose = 'RETAIN') as grade_retain, max(grade) filter (where purpose = 'ACTIVATE') as grade_activate
    from {{ ref('dq_scorecard_market') }} where dimension = 'PURPOSE_SCORE' group by all

),

pop as (

    -- the denominator, if Anna loaded one: youth (5-17) population of the market's ZIP3, weighted by the allocation; the latest year at or before the participation year
    select m.club_market_id, p.year as pop_year, sum(m.allocation_weight * p.population) as youth_population, any_value(p.source_name) as source_name
    from {{ ref('club_market_map') }} m join {{ ref('population_denominators') }} p on p.zip3 = m.zip3
    group by all

)

select
    p.club_market_id,
    coalesce(mm.market_name, case p.club_market_id when 'OUTSIDE_US' then 'Outside the US' when 'UNALLOCATED' then 'Unallocated' end) as market_name,
    p.participation_year,
    round(p.participants_allocated, 1)                                      as participants_allocated,
    round(coalesce(p.participants_zip_placed, 0), 1)                        as participants_zip_placed,
    round(coalesce(p.participants_unplaced_allocated, 0), 1)                as participants_unplaced_allocated,
    round(coalesce(p.participants_outside_us, 0), 1)                        as participants_outside_us,
    round(coalesce(p.youth_participants_allocated, 0), 1)                   as youth_participants_allocated,
    round(coalesce(o.orgs_known, 0), 2)                                     as orgs_known,
    round(coalesce(o.orgs_reporting, 0), 2)                                 as orgs_reporting,
    round(coalesce(o.orgs_dark, 0), 2)                                      as orgs_dark,
    round(coalesce(c.coverage_low, 0), 1)                                   as coverage_low,
    round(coalesce(c.coverage_point, 0), 1)                                 as coverage_point,
    round(coalesce(c.coverage_high, 0), 1)                                  as coverage_high,
    round(p.participants_allocated + coalesce(c.coverage_low, 0), 1)        as interval_low,
    round(p.participants_allocated + coalesce(c.coverage_high, 0), 1)       as interval_high,
    round(g.pct_records_geo_fit, 4)                                         as pct_records_geo_fit,
    gr.grade_count, gr.grade_segment, gr.grade_geo, gr.grade_retain, gr.grade_activate,
    pp.youth_population,
    case when pp.youth_population is null then 'denominator not loaded' else 'illustrative only: synthetic participant counts over real population denominators (' || pp.source_name || ')' end as denominator_status,
    case when pp.youth_population is null then null else round(p.youth_participants_allocated / pp.youth_population, 5) end as participation_rate
from people p
left join orgs o using (club_market_id, participation_year)
left join cov c using (club_market_id, participation_year)
left join geo g using (club_market_id, participation_year)
left join grades gr using (club_market_id, participation_year)
left join (select distinct club_market_id as cm, market_name from {{ ref('club_market_map') }}) mm on mm.cm = p.club_market_id
left join (select club_market_id, youth_population, source_name, pop_year from pop qualify row_number() over (partition by club_market_id order by pop_year desc) = 1) pp on pp.club_market_id = p.club_market_id and pp.pop_year <= p.participation_year
