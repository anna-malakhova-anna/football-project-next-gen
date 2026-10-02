-- One row per record per block it belongs to. Blocking limits comparisons to plausible candidates:
--   B1 birth_year + first 3 chars of last name     most re-registrations, typos in the first name
--   B2 contact_email + birth_year                  name changes, nicknames
--   B3 contact_phone + birth_year                  email changed between seasons
--   B4 last name + first name (any birth year)     swapped day/month, CA birth-year errors, cross-border
--   B5 contact_email + first initial               birth-year errors where the email is stable
-- Deliberately no block on exact dob alone (too coarse for common birthdays). Null keys never block.
with r as (select * from {{ ref('idr_input_records') }})

select match_record_id, 'B1' as block, birth_year::varchar || '|' || left(last_name_key, 3) as block_key
from r where birth_year is not null and nullif(last_name_key, '') is not null
union all
select match_record_id, 'B2', contact_email || '|' || birth_year::varchar
from r where contact_email is not null and birth_year is not null
union all
select match_record_id, 'B3', contact_phone || '|' || birth_year::varchar
from r where contact_phone is not null and birth_year is not null
union all
select match_record_id, 'B4', last_name_key || '|' || first_name_key
from r where nullif(last_name_key, '') is not null and nullif(first_name_key, '') is not null
union all
select match_record_id, 'B5', contact_email || '|' || left(first_name_key, 1)
from r where contact_email is not null and nullif(first_name_key, '') is not null
