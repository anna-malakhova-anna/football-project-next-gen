{{ config(tags=['phase5']) }}
-- GROUND TRUTH (evaluation only). Does the label-free scorecard recover the latent profile the generator gave each organization? Mean purpose score by profile, and the share of each profile
-- graded C or D, for REPORTING organizations (a dark organization is scored by coverage, not quality). If the scorecard works, DISCIPLINED scores highest and MANUAL lowest, and the grades separate them.
-- The profile is never an input to the scorecard; this model only compares the two afterwards.
select
    t.profile,
    s.purpose,
    count(distinct s.source_system || '|' || s.org_id)                      as organizations,
    round(avg(s.score), 2)                                                  as mean_purpose_score,
    round(avg((s.grade in ('C', 'D'))::int), 4)                             as share_graded_c_or_d,
    round(avg((s.grade = 'D')::int), 4)                                     as share_graded_d
from {{ ref('dq_scorecard_org') }} s
join {{ source('ground_truth', 'org_quality_truth') }} t on t.source_system = s.source_system and t.org_id = s.org_id
where s.dimension = 'PURPOSE_SCORE' and s.reported and s.source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED')
group by 1, 2
