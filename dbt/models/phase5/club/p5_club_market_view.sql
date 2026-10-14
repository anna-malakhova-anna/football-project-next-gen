-- depends_on: {{ ref('p5_params') }}
-- CLUB-FACING. One row per club and market in its territory: the participation estimate with its band, the
-- confidence, the market's data quality grade, and its top data gaps. Aggregate only: one row is a market, never a child. A rounded estimate between 1 and club_min_cell - 1 is suppressed
-- (every number NULL, status SUPPRESSED); a market with no children observed is NO_DATA, not zero. A SHARED market shows the same market-level figures to each club that shares it.
with gaps as (

    select
        market_id,
        array_to_string(list_slice(list(description || ': ' || round(100 * pass_rate)::integer::varchar || '% of records pass; the bar is ' || round(100 * coalesce(threshold_participation_reporting, threshold_club_activation))::integer::varchar || '%'
                                        order by (coalesce(threshold_participation_reporting, threshold_club_activation) - pass_rate) desc), 1, 3), '; ') as top_data_gaps
    from {{ ref('dq_rule_results_market') }}
    where pass_rate is not null
      and (pass_rate < coalesce(threshold_participation_reporting, 0) or pass_rate < coalesce(threshold_club_activation, 0))
    group by 1

),

base as (

    select
        t.club_id, c.club_name, t.market_id, e.market_name, t.role as club_market_role,
        round(e.estimate)::integer as est, round(e.estimate_low)::integer as lo, round(e.estimate_high)::integer as hi,
        e.confidence,
        m.grade as data_quality_grade, m.fit_for_participation_reporting, g.top_data_gaps
    from {{ ref('p5_club_territory') }} t
    join {{ ref('p5_club') }} c using (club_id)
    join {{ ref('p5_market_estimate') }} e using (market_id)
    left join {{ ref('dq_score_market') }} m using (market_id)
    left join gaps g using (market_id)

)

select
    club_id, club_name, market_id, market_name, club_market_role,
    case when est is null then 'NO_DATA' when est > 0 and est < {{ p5_param('club_min_cell') }} then 'SUPPRESSED' else 'PUBLISHED' end as status,
    case when est >= {{ p5_param('club_min_cell') }} then est end                                         as participation_estimate,
    case when est >= {{ p5_param('club_min_cell') }} then lo end                                          as estimate_low,
    case when est >= {{ p5_param('club_min_cell') }} then hi end                                          as estimate_high,
    confidence,
    data_quality_grade,
    fit_for_participation_reporting,
    top_data_gaps
from base
