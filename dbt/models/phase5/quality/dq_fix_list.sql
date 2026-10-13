-- The league-level fix list: for each league, the top issues an operator can act on, worst shortfall first.
-- shortfall = how far the pass rate is below the activation threshold (or the reporting threshold where a rule has no activation threshold), times the records failing.
-- A rule appears only when it misses a threshold. fix_text is written in the rules seed with {n_fail}, {pct} and {n} filled in here.
with ranked as (

    select
        league_group, rule_id, dimension, n_evaluated, n_fail, pass_rate, fix_text,
        coalesce(threshold_club_activation, threshold_participation_reporting) as threshold,
        coalesce(threshold_club_activation, threshold_participation_reporting) - pass_rate as shortfall,
        (threshold_participation_reporting is not null and pass_rate < threshold_participation_reporting) as blocks_reporting,
        (threshold_club_activation is not null and pass_rate < threshold_club_activation) as blocks_activation
    from {{ ref('dq_rule_results_league') }}
    where pass_rate is not null
      and (pass_rate < coalesce(threshold_participation_reporting, 0) or pass_rate < coalesce(threshold_club_activation, 0))

),

ordered as (

    select
        *,
        row_number() over (partition by league_group order by shortfall * n_fail desc, rule_id) as fix_rank
    from ranked

)

select
    o.league_group,
    s.league_name,
    o.fix_rank,
    o.rule_id,
    o.dimension,
    o.blocks_reporting,
    o.blocks_activation,
    o.n_fail,
    o.n_evaluated,
    round(o.pass_rate, 4)                                                   as pass_rate,
    o.threshold,
    replace(replace(replace(o.fix_text, '{n_fail}', o.n_fail::varchar), '{pct}', round(100.0 * o.n_fail / o.n_evaluated, 1)::varchar || '%'), '{n}', o.n_evaluated::varchar) as fix
from ordered o
join {{ ref('dq_score_league') }} s using (league_group)
where o.fix_rank <= 3
