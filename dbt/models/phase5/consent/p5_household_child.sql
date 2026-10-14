-- RESTRICTED BRIDGE. household_id <-> p5_person_id. The only link between the parent side and the child side. No activation, funnel or club-facing model reads it
-- except to COUNT children; the test p5_activation_chain_never_touches_the_child checks the columns of everything downstream.
select distinct h.household_id, r.p5_person_id
from {{ ref('p5_record_person') }} r
join {{ ref('p5_household') }} h on h.contact_email = r.contact_email
