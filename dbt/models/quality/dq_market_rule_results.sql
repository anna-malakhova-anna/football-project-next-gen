-- depends_on: {{ ref('dq_rule_registry') }}
-- depends_on: {{ ref('dq_record_resolved') }}
-- depends_on: {{ ref('dq_org_season_base') }}
-- depends_on: {{ ref('int_participant_year_market') }}
-- depends_on: {{ ref('club_market_map') }}
-- The rule results at CLUB-MARKET grain (rule x club market x season x purpose): the same registry rules, evaluated over the records of the participants allocated to each market, with allocated
-- (fractional) counts. Contract rules have no market (they are measured once per source) and standard rules are INFO; neither is here. OUTSIDE_US holds the Canadian and international participants.
with measured as ({{ dq_market_rule_results() }}),

expanded as (

    select m.rule_id, m.club_market_id, m.season_year, m.n_evaluated, m.n_pass, m.n_pass / nullif(m.n_evaluated, 0) as pass_rate,
           g.dimension, g.severity, g.origin,
           unnest(case when coalesce(g.purposes, '') = '' then [cast(null as varchar)] else string_split(g.purposes, '|') end) as purpose,
           g.threshold_count, g.threshold_segment, g.threshold_geo, g.threshold_retain, g.threshold_activate
    from measured m join {{ ref('dq_rule_registry') }} g using (rule_id)

)

select
    rule_id, dimension, origin, club_market_id, season_year, purpose,
    round(n_evaluated, 4) as n_evaluated, round(n_pass, 4) as n_pass,
    round(pass_rate, 6) as observed_value,
    {{ dq_threshold_for('purpose') }} as threshold,
    case when n_evaluated is null or n_evaluated = 0 or ({{ dq_threshold_for('purpose') }}) is null then null else pass_rate >= ({{ dq_threshold_for('purpose') }}) end as pass,
    severity
from expanded
