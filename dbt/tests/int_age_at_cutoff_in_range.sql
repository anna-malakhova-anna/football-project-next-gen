-- age_at_cutoff must be between 3 and 80 for every record not flagged is_impossible_dob.
select registration_key, source_system, age_at_cutoff
from {{ ref('int_registrations_unioned') }}
where not coalesce(is_impossible_dob, false)
  and (age_at_cutoff is null or age_at_cutoff < 3 or age_at_cutoff > 80)
