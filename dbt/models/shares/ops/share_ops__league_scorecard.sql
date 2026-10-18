{{ config(tags=['phase6']) }}
-- OPS share, DP1 output port (Phase 6): the quality scorecard of each LEAGUE (an organization, never a person) per season and purpose: score, grade, how many records it sent, whether it sent a file, which check
-- limits the score and its top failing problems in plain words. AGGREGATE per organization: no participant, household or contact field. A league with a score is graded on the lower bound of its interval.
with p as (

    select s.season_year, s.source_system, s.org_id, s.purpose,
           string_agg(coalesce(r.plain_label, t.rule_id), '; ' order by t.ord) as top_problems_plain
    from {{ ref('dq_scorecard_org') }} s
    cross join unnest(coalesce(s.top_failing_rules, []::varchar[])) with ordinality as t(rule_id, ord)
    left join {{ ref('dq_rule_registry') }} r on r.rule_id = t.rule_id
    where s.dimension = 'PURPOSE_SCORE'
    group by 1, 2, 3, 4

)

select
    s.season_year, s.source_system, s.org_id, s.org_name, s.channel, s.purpose,
    round(s.score, 1)                                                       as score,
    s.grade,
    s.record_count,
    s.reported,
    s.limiting_dimension,
    coalesce(p.top_problems_plain, '')                                      as top_problems_plain
from {{ ref('dq_scorecard_org') }} s
left join p on p.season_year = s.season_year and p.source_system = s.source_system and p.org_id = s.org_id and p.purpose = s.purpose
where s.dimension = 'PURPOSE_SCORE' and s.score is not null
order by s.season_year, s.source_system, s.org_id, s.purpose
