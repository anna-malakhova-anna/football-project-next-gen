-- RESTRICTED. One row per in-scope feed record: the resolved child and the record's usable parent email. This is the only place a record, a child and a parent contact meet.
-- A usable email is well formed after trimming and lower-casing; anything else is NULL (the record then belongs to no household).
select
    s.feed,
    s.source_record_id,
    c.p5_person_id,
    case when regexp_matches(s.contact_email, '^[^@\s]+@[^@\s]+\.[a-z]{2,}$') then s.contact_email end as contact_email,
    s.registered_at,
    s.season_year
from {{ ref('stg_p5_registrations') }} s
join {{ ref('p5_idr_input_records') }} i on i.content_hash = s.content_hash
join {{ ref('p5_clusters') }} c on c.match_record_id = i.match_record_id
where s.is_flag
