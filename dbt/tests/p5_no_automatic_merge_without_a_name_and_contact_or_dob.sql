{{ config(tags=['phase5']) }}
-- Precision first: an automatic Phase 5 merge needs the last name to agree exactly and the first name to agree (exactly or as a nickname) with DOB or parent email
-- support. The sibling guard R4 (same email and DOB, different first name) must never be an automatic merge.
select record_a, record_b, rule_id from {{ ref('p5_pair_scores') }}
where tier = 'AUTO_MATCH' and rule_id not in ('R1', 'R2', 'R7')
