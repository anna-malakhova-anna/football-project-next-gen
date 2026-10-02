-- GROUND TRUTH (evaluation only). The true person, household and twin group behind each input record.
select
    i.match_record_id,
    t.true_person_id,
    p.household_id,
    p.twin_group_id,
    i.source_system
from {{ ref('idr_input_records') }} i
join {{ source('ground_truth', 'registration_truth') }} t
    on t.source_system = i.source_system and t.source_record_id = i.source_record_id
join {{ source('ground_truth', 'person_registry') }} p on p.true_person_id = t.true_person_id
