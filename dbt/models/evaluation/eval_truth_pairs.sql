-- GROUND TRUTH (evaluation only). Every true matching pair among the matcher's input records: two surviving
-- records of the same true person. Collapsed exact duplicates are already one record, so each true person with
-- n input records contributes n(n-1)/2 pairs. This is the denominator for recall.
with truth as (

    select i.match_record_id, i.source_system, i.country_code, t.true_person_id
    from {{ ref('idr_input_records') }} i
    join {{ source('ground_truth', 'registration_truth') }} t
        on t.source_system = i.source_system and t.source_record_id = i.source_record_id

)

select
    a.match_record_id                                                       as record_a,
    b.match_record_id                                                       as record_b,
    a.true_person_id,
    {{ source_pair('a.source_system', 'b.source_system') }}                 as source_pair,
    d.record_a is not null                                                  as is_deterministic
from truth a
join truth b on a.true_person_id = b.true_person_id and a.match_record_id < b.match_record_id
left join {{ ref('idr_deterministic_links') }} d on d.record_a = a.match_record_id and d.record_b = b.match_record_id
