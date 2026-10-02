{{ config(tags=['phase2']) }}
-- Every candidate pair is ordered record_a < record_b (so no self-pairs), appears once, is never also a
-- deterministic link, and has exactly one feature row.
select 'unordered_or_self' as problem, record_a, record_b from {{ ref('idr_candidate_pairs') }} where record_a >= record_b
union all
select 'duplicate_pair', record_a, record_b from {{ ref('idr_candidate_pairs') }} group by 2, 3 having count(*) > 1
union all
select 'also_deterministic', c.record_a, c.record_b from {{ ref('idr_candidate_pairs') }} c
    join {{ ref('idr_deterministic_links') }} d using (record_a, record_b)
union all
select 'feature_row_count_differs', null, null
where (select count(*) from {{ ref('idr_candidate_pairs') }}) <> (select count(*) from {{ ref('idr_pair_features') }})
