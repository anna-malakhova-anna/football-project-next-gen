-- depends_on: {{ ref('dq_org_season_base') }}
-- DP3 (it counts participants, so it reads DP2's person-grain registrations and DP1's organization base). For every KNOWN organization that sent no file in a season, the number of unique participants it probably had: the median (and 25th / 75th percentile) of the unique participants of REPORTING
-- peers of the same source, season, size band and region. The size band comes from the organization's own other seasons (terciles of its mean record count; UNKNOWN if it never reported).
-- Falls back to the same size band in any region, then to any peer, when fewer than three peers exist (peer_level says which). An ESTIMATE with an interval, not a bound; gross of participants who
-- also played at a reporting organization that year. Label-free: no answer key. Read by mart_uncertainty_decomposition (summed per year) and by the club-market coverage (spread over markets).
with org_year as (

    select b.source_system, b.organization_id as org_id, b.participation_year as season_year, count(distinct b.participant_id) as participants, o.region_code
    from {{ ref('fct_registration') }} b join {{ ref('dq_org_season_base') }} o on o.source_system = b.source_system and o.org_id = b.organization_id and o.season_year = b.participation_year
    where b.source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED') and b.participant_id is not null group by all

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

    select o.source_system, o.org_id, o.season_year, o.region_code, o.zip3, b.size_band
    from {{ ref('dq_org_season_base') }} o join banded b using (source_system, org_id)
    where not o.reported and o.source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED')

),

estimates as (

    select
        d.source_system, d.org_id, d.season_year, d.region_code, d.zip3,
        (select count(*) from peers p where p.source_system = d.source_system and p.season_year = d.season_year and p.size_band = d.size_band and p.region_code = d.region_code) as n_same_band_region,
        (select count(*) from peers p where p.source_system = d.source_system and p.season_year = d.season_year and p.size_band = d.size_band) as n_same_band,
        (select quantile_cont(p.participants, [0.25, 0.5, 0.75]) from peers p where p.source_system = d.source_system and p.season_year = d.season_year
            and p.size_band = d.size_band and p.region_code = d.region_code) as q_band_region,
        (select quantile_cont(p.participants, [0.25, 0.5, 0.75]) from peers p where p.source_system = d.source_system and p.season_year = d.season_year and p.size_band = d.size_band) as q_band,
        (select quantile_cont(p.participants, [0.25, 0.5, 0.75]) from peers p where p.source_system = d.source_system and p.season_year = d.season_year) as q_any
    from dark d

)

select
    source_system, org_id, season_year, region_code, zip3,
    q[1] as q25, q[2] as q50, q[3] as q75,
    peer_level
from (
    select source_system, org_id, season_year, region_code, zip3,
           case when n_same_band_region >= 3 then q_band_region when n_same_band >= 3 then q_band else q_any end as q,
           case when n_same_band_region >= 3 then 'SAME_BAND_AND_REGION' when n_same_band >= 3 then 'SAME_BAND' else 'ANY_PEER' end as peer_level
    from estimates
)
