-- Same blocks as idr_blocking_keys except the phone block (no Phase 5 feed carries a phone):
--   B1 birth_year + first 3 chars of last name   B2 contact_email + birth_year   B4 last name + first name   B5 contact_email + first initial
-- Feeds without a DOB (vendor_reg_b, school_program) reach candidates only through B4 and B5. Null keys never block.
with r as (select * from {{ ref('p5_idr_input_records') }})

select match_record_id, 'B1' as block, birth_year::varchar || '|' || left(last_name_key, 3) as block_key
from r where birth_year is not null and nullif(last_name_key, '') is not null
union all
select match_record_id, 'B2', contact_email || '|' || birth_year::varchar
from r where contact_email is not null and birth_year is not null
union all
select match_record_id, 'B4', last_name_key || '|' || first_name_key
from r where nullif(last_name_key, '') is not null and nullif(first_name_key, '') is not null
union all
select match_record_id, 'B5', contact_email || '|' || left(first_name_key, 1)
from r where contact_email is not null and nullif(first_name_key, '') is not null
