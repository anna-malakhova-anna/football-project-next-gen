-- RESTRICTED. For each household and purpose, the LATEST consent event decides (by event time, else registration time); on a tie a DENIED wins. An event whose status is UNKNOWN
-- (wording not interpretable) grants nothing and denies nothing and is ignored here: not captured is not false. The provenance of the deciding event travels with it.
with per_purpose as (

    select
        e.household_id, p.purpose, e.status, e.event_kind, e.provenance_known, e.when_known, e.which_known, e.what_known,
        coalesce(e.event_ts, e.registered_at) as decided_at
    from {{ ref('p5_consent_event') }} e, unnest(e.purposes) as p(purpose)
    where e.household_id is not null and e.status in ('GRANTED', 'DENIED')

),

ranked as (

    select *, row_number() over (partition by household_id, purpose order by decided_at desc, (status = 'DENIED') desc) as rn
    from per_purpose

)

select household_id, purpose, status, event_kind, decided_at, provenance_known, what_known, when_known, which_known
from ranked where rn = 1
