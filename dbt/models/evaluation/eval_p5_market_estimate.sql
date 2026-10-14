{{ config(tags=['phase5']) }}
-- GROUND TRUTH (evaluation only). The market estimate against the true number of children registered in the latest season whose home is in the market, and against the naive count
-- (children observed with a usable ZIP, nothing allocated, no band). Never used to tune the method: the band parameters are fixed in config.
with latest as (select max(season_year) as s from {{ ref('stg_p5_registrations') }}),

truth as (

    select p.home_market_id as market_id, count(distinct t.true_person_id) as true_children
    from {{ source('ground_truth', 'p5_registration_truth') }} t
    join {{ source('ground_truth', 'person_registry') }} p on p.true_person_id = t.true_person_id
    where t.is_flag and t.season_year = (select s from latest)
    group by 1

)

select
    e.market_id, e.club_coverage, e.confidence,
    e.placed_children                                                       as naive_count,
    e.estimate, e.estimate_low, e.estimate_high,
    coalesce(t.true_children, 0)                                            as true_children,
    e.estimate_low <= coalesce(t.true_children, 0) and coalesce(t.true_children, 0) <= e.estimate_high as band_contains_truth,
    round(abs(e.estimate - coalesce(t.true_children, 0)) / nullif(t.true_children, 0), 4) as estimate_error,
    round(abs(e.placed_children - coalesce(t.true_children, 0)) / nullif(t.true_children, 0), 4) as naive_error
from {{ ref('p5_market_estimate') }} e
left join truth t using (market_id)
where e.estimate is not null
