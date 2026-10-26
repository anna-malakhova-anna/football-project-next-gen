-- depends_on: {{ ref('p7_params') }}
-- Direction per program market (ADR-025 section 2), latest season pair. Participation direction only for MEASURED and PARTIAL markets:
--   like for like   growth counts only organizations with participants in BOTH seasons (DP3's mart_participation_by_org)
--   noise floor     sigma = sample standard deviation of like-for-like growth over every MEASURED market and every season pair BEFORE the latest
--                   (pairs below the organization minimum excluded); pooled because no market has more than four pairs
--   label           GROWING above z * sigma, SHRINKING below -z * sigma, else FLAT; NOT_DETECTABLE below the organization minimum or with too few pooled
--                   pairs; NOT_MEASURED for PROXY_ONLY and DARK markets
--   proxy           sign of the change in club events + games between the two latest seasons (UNKNOWN when events are blank, NO_PROXY with no return),
--                   shown BESIDE the participation direction and never combined with it (ADR-015)
with latest as (select last_observed_year as y1, last_observed_year - 1 as y0 from {{ ref('observation_window') }}),

status as (select * from {{ ref('mart_gmp_market_status') }}),

pairs as (

    select a.country_code, b.participation_year as season_year, count(*) as orgs_both,
           sum(a.participants) as participants_prev, sum(b.participants) as participants_now
    from {{ ref('mart_participation_by_org') }} a
    join {{ ref('mart_participation_by_org') }} b
      on b.org_id = a.org_id and b.source_system = a.source_system and b.participation_year = a.participation_year + 1
    where a.participants > 0 and b.participants > 0
    group by 1, 2

),

growth as (

    select p.*, (participants_now - participants_prev)::double / participants_prev as growth
    from pairs p join status s using (country_code)

),

pool as (

    select stddev_samp(g.growth) as sigma, count(*) as pooled_pairs
    from growth g join status s using (country_code)
    where s.status = 'MEASURED' and g.season_year < (select y1 from latest) and g.orgs_both >= {{ p7_param('min_orgs_both_seasons') }}

),

proxy as (

    select country_code,
           max(case when season_year = (select y0 from latest) then club_events + games_in_market end) as proxy_prev,
           max(case when season_year = (select y1 from latest) then club_events + games_in_market end) as proxy_now,
           count(*) filter (where season_year in ((select y0 from latest), (select y1 from latest))) as proxy_returns
    from {{ ref('stg_gmp_proxy') }} where not is_superseded group by 1

),

labelled as (

    select
        s.country_code, s.status, s.season_year,
        g.orgs_both, g.participants_prev, g.participants_now, round(g.growth, 6) as growth,
        round(pl.sigma, 6) as noise_floor, pl.pooled_pairs,
        round({{ p7_param('z') }} * pl.sigma, 6) as minimum_detectable_change,
        case
            when s.status not in ('MEASURED', 'PARTIAL') then 'NOT_MEASURED'
            when pl.pooled_pairs < {{ p7_param('min_pooled_pairs') }} or g.growth is null or g.orgs_both < {{ p7_param('min_orgs_both_seasons') }} then 'NOT_DETECTABLE'
            when g.growth > {{ p7_param('z') }} * pl.sigma then 'GROWING'
            when g.growth < -{{ p7_param('z') }} * pl.sigma then 'SHRINKING'
            else 'FLAT'
        end as participation_direction,
        case
            when coalesce(x.proxy_returns, 0) = 0 then 'NO_PROXY'
            when x.proxy_prev is null or x.proxy_now is null then 'UNKNOWN'
            when x.proxy_now > x.proxy_prev then 'GROWING'
            when x.proxy_now < x.proxy_prev then 'SHRINKING'
            else 'FLAT'
        end as proxy_direction
    from status s
    cross join pool pl
    left join growth g on g.country_code = s.country_code and g.season_year = s.season_year
    left join proxy x on x.country_code = s.country_code

)

select
    *,
    case
        when participation_direction in ('NOT_MEASURED', 'NOT_DETECTABLE') then 'NOT_APPLICABLE'
        when proxy_direction in ('NO_PROXY', 'UNKNOWN') then 'NO_PROXY'
        when proxy_direction = participation_direction then 'AGREE'
        else 'DISAGREE'
    end as proxy_agreement,
    case when status = 'MEASURED' then rank() over (partition by status = 'MEASURED' order by growth desc nulls last, country_code) end as growth_rank
from labelled
order by country_code
