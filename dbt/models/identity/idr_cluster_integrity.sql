-- Transitive chains are how siblings get merged (A~B, B~C, but A is not C). For the active matcher's final clusters
-- (var matcher, stage POST_REVIEW, scope AUTO) flag any cluster that shows one of these symptoms:
--   DOB_CONFLICT       two day-precision DOBs more than 1 day apart that are not a day/month swap
--   SEX_CONFLICT       both F and M present
--   SIBLING_IN_CLUSTER two records in the same org and season with different first names
--   OVERSIZE           more members than one person could plausibly have (macro idr_plausible_max_cluster_size)
--   WEAK_BRIDGE        a pair inside the cluster that the active matcher itself scored NON_MATCH
-- Each flagged cluster lists its issues and goes to the review queue. Reads no ground truth.
{% set matcher = var('matcher') %}
with c as (

    select cluster_id, match_record_id, cluster_size
    from {{ ref('idr_clusters') }}
    where matcher = '{{ matcher }}' and stage = 'POST_REVIEW' and scope = 'AUTO' and cluster_size > 1

),

m as (

    select c.cluster_id, c.cluster_size, r.*
    from c join {{ ref('idr_input_records') }} r on r.match_record_id = c.match_record_id

),

pairs as (

    select a.cluster_id, a.cluster_size, a.match_record_id as ra, b.match_record_id as rb,
           a.dob as a_dob, b.dob as b_dob, a.sex as a_sex, b.sex as b_sex,
           a.organization_id as a_org, b.organization_id as b_org, a.season_key as a_season, b.season_key as b_season,
           a.first_name_key as a_first, b.first_name_key as b_first
    from m a join m b on a.cluster_id = b.cluster_id and a.match_record_id < b.match_record_id

),

scores as (

    select record_a, record_b, tier from {{ ref('idr_pair_scores_rules') }} where 'rules' = '{{ matcher }}'
    union all
    select record_a, record_b, tier from {{ ref('idr_pair_scores_fs') }} where matcher = '{{ matcher }}'

),

issues as (

    select cluster_id, cluster_size, 'DOB_CONFLICT' as issue
    from pairs
    where a_dob is not null and b_dob is not null and abs(a_dob - b_dob) > 1
      and not (extract(year from a_dob) = extract(year from b_dob)
               and extract(month from a_dob) = extract(day from b_dob)
               and extract(day from a_dob) = extract(month from b_dob))
    union all
    select cluster_id, cluster_size, 'SEX_CONFLICT'
    from pairs where a_sex <> 'U' and b_sex <> 'U' and a_sex <> b_sex
    union all
    select cluster_id, cluster_size, 'SIBLING_IN_CLUSTER'
    from pairs
    where a_org = b_org and a_season = b_season and {{ name_similarity('a_first', 'b_first', 'first') }} = 'DIFFERENT'
    union all
    select cluster_id, cluster_size, 'OVERSIZE'
    from pairs where cluster_size > {{ idr_plausible_max_cluster_size() }}
    union all
    select p.cluster_id, p.cluster_size, 'WEAK_BRIDGE'
    from pairs p join scores s on s.record_a = p.ra and s.record_b = p.rb and s.tier = 'NON_MATCH'
    -- a pair a steward has confirmed as a match is no longer a weak bridge
    left join {{ ref('review_decisions') }} d
        on d.decision = 'MATCH' and least(d.record_a, d.record_b) = p.ra and greatest(d.record_a, d.record_b) = p.rb
    where d.record_a is null

)

select
    '{{ matcher }}'                                                         as matcher,
    cluster_id,
    max(cluster_size)                                                       as cluster_size,
    list_sort(list_distinct(list(issue)))                                   as integrity_issues,
    (select list(match_record_id order by match_record_id) from c where c.cluster_id = issues.cluster_id) as member_record_ids
from issues
group by cluster_id
