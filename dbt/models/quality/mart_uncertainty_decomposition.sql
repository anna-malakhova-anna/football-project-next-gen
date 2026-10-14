-- depends_on: {{ ref('observation_window') }}
-- Why there is no single number (phase-5-spec 6.1, ADR-015): the participant count is uncertain for three DIFFERENT reasons, and they are shown SIDE BY SIDE, never added.
--   IDENTITY       Phase 3 low / point / high: how many people the records are, depending on which uncertain links are real. (label-free)
--   DQ_EXCLUSIONS  strict vs lenient handling of records that fail a COUNT rule of the registry: lenient is the Phase 3 count; strict counts only participants who have at least one record
--                  fit for COUNT (dq_record_fitness). (label-free)
--   COVERAGE       participants of KNOWN organizations that sent no file that season: for each dark organization the median (and 25th / 75th percentiles) of the unique participants of reporting
--                  organizations of the same source, season, size band and region, where the size band comes from the organization's own other seasons. Falls back to the same size band in any
--                  region, then to any organization, when fewer than three peers exist. An ESTIMATE with an interval, not a bound, and not independent of the other components. (label-free)
-- Columns: point / low / high are in the component's own quantity (participants counted, or participants missing from the data). interval_low / interval_high put each on the participant scale
-- (coverage: reported point + the missing participants) so the three can be drawn as separate bars around the reported count. contribution = interval width. No row and no column sums components.
with reported as (

    select participation_year, participants_low, participants_point, participants_high
    from {{ ref('mart_identity_uncertainty') }} where grain = 'GLOBAL'

),

lenient as (

    select participation_year, count(distinct participant_id) as participants from {{ ref('fct_participant_year') }} group by 1

),

strict as (

    select season_year as participation_year, count(distinct person_id) as participants
    from {{ ref('dq_record_fitness') }} where fit_for_count and source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') group by 1

),

-- ---- coverage ----
org_year as (

    select b.source_system, b.org_id, b.season_year, count(distinct b.person_id) as participants, o.region_code
    from {{ ref('dq_record_base') }} b join {{ ref('dq_org_season_base') }} o on o.source_system = b.source_system and o.org_id = b.org_id and o.season_year = b.season_year
    where b.source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') and b.person_id is not null group by all

),

org_size as (

    select source_system, org_id, avg(n_records) filter (where reported) as mean_records from {{ ref('dq_org_season_base') }}
    where source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') group by 1, 2

),

banded as (

    select *, case when mean_records is null then 'UNKNOWN' else 'B' || ntile(3) over (partition by source_system order by mean_records) end as size_band from org_size

),

peers as (

    select y.source_system, y.season_year, y.org_id, y.participants, y.region_code, b.size_band from org_year y join banded b using (source_system, org_id)

),

dark as (

    select o.source_system, o.org_id, o.season_year, o.region_code, b.size_band
    from {{ ref('dq_org_season_base') }} o join banded b using (source_system, org_id)
    where not o.reported and o.source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED')

),

estimates as (

    select
        d.source_system, d.org_id, d.season_year,
        (select count(*) from peers p where p.source_system = d.source_system and p.season_year = d.season_year and p.size_band = d.size_band and p.region_code = d.region_code) as n_same_band_region,
        (select count(*) from peers p where p.source_system = d.source_system and p.season_year = d.season_year and p.size_band = d.size_band) as n_same_band,
        (select quantile_cont(p.participants, [0.25, 0.5, 0.75]) from peers p where p.source_system = d.source_system and p.season_year = d.season_year
            and p.size_band = d.size_band and p.region_code = d.region_code) as q_band_region,
        (select quantile_cont(p.participants, [0.25, 0.5, 0.75]) from peers p where p.source_system = d.source_system and p.season_year = d.season_year and p.size_band = d.size_band) as q_band,
        (select quantile_cont(p.participants, [0.25, 0.5, 0.75]) from peers p where p.source_system = d.source_system and p.season_year = d.season_year) as q_any
    from dark d

),

picked as (

    select source_system, org_id, season_year,
           case when n_same_band_region >= 3 then q_band_region when n_same_band >= 3 then q_band else q_any end as q,
           case when n_same_band_region >= 3 then 'SAME_BAND_AND_REGION' when n_same_band >= 3 then 'SAME_BAND' else 'ANY_PEER' end as peer_level
    from estimates

),

coverage as (

    select season_year as participation_year, count(*) as dark_orgs,
           sum(q[1]) as low, sum(q[2]) as point, sum(q[3]) as high,
           count(*) filter (where peer_level <> 'SAME_BAND_AND_REGION') as orgs_with_wider_peer_group
    from picked group by 1

)

select participation_year, 'IDENTITY' as component, 'participants counted' as quantity,
       participants_point::double as point, participants_low::double as low, participants_high::double as high,
       participants_point::double as reported_point,
       participants_low::double as interval_low, participants_high::double as interval_high,
       (participants_high - participants_low)::double as contribution,
       'Phase 3 bounds: connected components with PROBABLE links merged (low) or flagged clusters split (high)' as method, true as label_free
from reported
union all
select r.participation_year, 'DQ_EXCLUSIONS', 'participants counted', l.participants::double, s.participants::double, l.participants::double, r.participants_point::double,
       s.participants::double, l.participants::double, (l.participants - s.participants)::double,
       'strict (only participants with a record fit for COUNT) vs lenient (Phase 3: every valid registration)', true
from reported r join lenient l using (participation_year) join strict s using (participation_year)
union all
select r.participation_year, 'COVERAGE', 'participants missing from the data', c.point, c.low, c.high, r.participants_point::double,
       r.participants_point + c.low, r.participants_point + c.high, c.high - c.low,
       'dark organizations (' || c.dark_orgs || '; ' || c.orgs_with_wider_peer_group || ' with a wider peer group) x median unique participants of reporting peers of the same size band and region, interval = 25th to 75th percentile', true
from reported r join coverage c using (participation_year)
