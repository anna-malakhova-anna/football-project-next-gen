-- age_at_cutoff must be between 3 and 80 for every record not flagged is_impossible_dob. A record whose file carries no DOB (dob_age_group_only: the division gives an
-- age band only) has an unknown age by design; it is exempt, and only it.
select registration_key, source_system, age_at_cutoff
from {{ ref('int_registrations_unioned') }}
where not coalesce(is_impossible_dob, false) and not list_contains(dq_flags, 'dob_age_group_only')
  and (age_at_cutoff is null or age_at_cutoff < 3 or age_at_cutoff > 80)
