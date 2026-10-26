-- depends_on: {{ ref('p7_params') }}
-- The PLANNING SCENARIO for program markets with no participation source (PROXY_ONLY and DARK), ADR-025 section 3. NOT a measurement:
-- never summed with, ranked against or charted beside measured values, and every row says so (scenario_label).
--   comparables   MEASURED markets in the same region and legal regime; else the same region; else every MEASURED market (comparable_basis)
--   per-club rate participants (DP3's attributed count, latest season) / clubs with rights, for each comparable
--   range         [lowest rate, highest rate] x the market's clubs with rights (one comparable: low = high, and single_comparable says so)
--   direction     the comparables' participation direction if they all agree, else MIXED
-- Reads no truth and no evaluation model (scripts/check_eval_isolation.py).
with status as (select * from {{ ref('mart_gmp_market_status') }}),

measured as (

    select s.country_code, s.region, s.legal_regime_id, s.clubs_with_rights, p.participants_attributed, d.participation_direction,
           p.participants_attributed::double / s.clubs_with_rights as per_club_rate
    from status s
    join {{ ref('share_exec__participation_by_country') }} p on p.country_code = s.country_code and p.participation_year = s.season_year
    join {{ ref('mart_gmp_direction') }} d on d.country_code = s.country_code
    where s.status = 'MEASURED' and p.participants_attributed is not null

),

targets as (select * from status where status in ('PROXY_ONLY', 'DARK')),

candidates as (

    select t.country_code, m.country_code as comparable, m.per_club_rate, m.participation_direction,
           case when m.region = t.region and m.legal_regime_id = t.legal_regime_id then 1 when m.region = t.region then 2 else 3 end as tier
    from targets t cross join measured m

),

chosen as (

    select c.* from candidates c
    where c.tier = (select min(c2.tier) from candidates c2 where c2.country_code = c.country_code)

)

select
    t.country_code, t.country_name, t.region, t.legal_regime_id, t.output_port, t.status, t.season_year, t.clubs_with_rights,
    case min(c.tier) when 1 then 'REGION_AND_REGIME' when 2 then 'REGION' else 'ALL' end      as comparable_basis,
    string_agg(c.comparable, '|' order by c.comparable)                                       as comparable_markets,
    count(*)                                                                                  as n_comparables,
    count(*) = 1                                                                              as single_comparable,
    round(min(c.per_club_rate) * t.clubs_with_rights)::bigint                                 as scenario_low,
    round(max(c.per_club_rate) * t.clubs_with_rights)::bigint                                 as scenario_high,
    case when count(distinct c.participation_direction) = 1 and min(c.participation_direction) in ('GROWING', 'SHRINKING', 'FLAT')
         then min(c.participation_direction) else 'MIXED' end                                 as scenario_direction,
    {{ p7_param('scenario_label', quote=true) }}                                              as scenario_label
from targets t join chosen c using (country_code)
group by t.country_code, t.country_name, t.region, t.legal_regime_id, t.output_port, t.status, t.season_year, t.clubs_with_rights
order by t.country_code
