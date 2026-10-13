-- depends_on: {{ ref('dq_rule_results_league') }}
-- Data quality scorecard per league: six dimension scores, an overall score and grade, and whether the league's data is fit for each purpose.
--   participation reporting (counts by market and age band): the lower bar     club activation (contactable households): the higher bar, and needs consent provenance
-- A league with fewer scored records than min_records_for_grade gets no grade. Every threshold is in the p5_dq_rules and p5_params seeds.
with scored as (

    {{ p5_score_columns("(select league_group as group_id, rule_id, n_evaluated, n_pass from " ~ ref('dq_rule_results_league') ~ ")") }}

),

counts as (

    select league_group as group_id, count(*) as n_records, count(distinct p5_person_id) as n_children, min(feed) as feed, min(league_id) as league_id
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
    s.group_id                                                              as league_group,
    c.league_id,
    coalesce(l.league_name, 'Unresolved league (' || c.feed || ')')         as league_name,
    c.feed,
    l.state,
    c.n_records,
    c.n_children,
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
left join {{ source('raw_p5', 'p5_league_catalog') }} l on l.league_id = c.league_id
