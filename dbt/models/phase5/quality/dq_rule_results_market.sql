-- depends_on: {{ ref('p5_record_quality') }}
-- Every rule evaluated for every market (placed by the child's home ZIP; UNPLACED when there is no usable ZIP). Same shape as dq_rule_results_league.
with results as (

    {{ p5_rule_results('market_id') }}

)

select
    r.group_id                                                              as market_id,
    r.rule_id,
    u.dimension,
    u.description,
    u.check_sql,
    r.n_evaluated,
    r.n_pass,
    r.n_evaluated - r.n_pass                                                as n_fail,
    r.n_pass::double / nullif(r.n_evaluated, 0)                             as pass_rate,
    u.threshold_participation_reporting,
    u.threshold_club_activation,
    u.fix_text
from results r join {{ ref('p5_dq_rules') }} u using (rule_id)
