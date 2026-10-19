-- DP2 (restricted port, consumer DP4). DP1's dq_record_base with the resolved-person facts of dq_identity_facts joined back on record_key: the SAME columns the one record-level stream had before it was
-- split between DP1 (what needs no person) and DP2 (what does). Streams with no resolved person (school, fan) carry NULL for the identity columns, which a rule reads as "not applicable".
select b.*, i.person_id, i.is_first_of_person_season, i.dob_consistent, i.sex_consistent, i.zip3_consistent, i.age_group_consistent
from {{ ref('dq_record_base') }} b
left join {{ ref('dq_identity_facts') }} i on i.record_key = b.record_key
