-- depends_on: {{ ref('dq_rule_results_market') }}
-- Data quality scorecard per market (the child's home ZIP3 -> market, via market_geo_map). Same measures as dq_score_league.
-- UNPLACED = no usable ZIP: the share of children no club can see at all is itself a finding. This table is for the data steward; the club-facing view,
-- with a minimum cell size, is built in step 5.
with scored as (

    {{ p5_score_columns("(select market_id as group_id, rule_id, n_evaluated, n_pass from " ~ ref('dq_rule_results_market') ~ ")") }}

),

counts as (

    select market_id as group_id, count(*) as n_records, count(distinct p5_person_id) as n_children, count(distinct league_group) as n_leagues
    from {{ ref('p5_record_quality') }}
    group by 1

),

params as (

    select
        max(case when param = 'min_records_for_grade' then value end)::integer as min_records,
        max(case when param = 'grade_a' then value end)::double as grade_a,
        max(case when param = 'grade_b' then value end)::double as grade_b,
        max(case when param = 'grade_c' then value end)::double as grade_c
    from {{ ref('p5_params') }}

)

select
    s.group_id                                                              as market_id,
    coalesce(m.market_name, case s.group_id when 'UNPLACED' then 'No usable ZIP' else 'ZIP not in any market' end) as market_name,
    m.region_code,
    c.n_records,
    c.n_children,
    c.n_leagues,
    round(s.completeness, 4) as completeness, round(s.validity, 4) as validity, round(s.uniqueness, 4) as uniqueness,
    round(s.timeliness, 4) as timeliness, round(s.consistency, 4) as consistency, round(s.consent_provenance, 4) as consent_provenance,
    round(s.overall_score, 4)                                               as overall_score,
    case when c.n_records < p.min_records then 'INSUFFICIENT_DATA'
         when s.overall_score >= p.grade_a then 'A' when s.overall_score >= p.grade_b then 'B' when s.overall_score >= p.grade_c then 'C' else 'D' end as grade,
    s.fit_for_participation_reporting,
    s.fit_for_club_activation,
    s.rules_failing_reporting,
    s.rules_failing_activation
from scored s
join counts c using (group_id)
cross join params p
left join {{ ref('market_map') }} m on m.market_id = s.group_id
