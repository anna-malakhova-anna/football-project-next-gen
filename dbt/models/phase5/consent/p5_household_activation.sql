-- RESTRICTED. Is a household eligible for club activation? Only through an explicit NFL_CLUB_MARKETING grant whose latest event is not a denial and whose provenance is complete
-- as far as p5_params requires (a timestamp, a wording). Consent for league operations or league communications NEVER makes a household eligible: purpose limitation.
-- would_be_eligible_if_comms_counted is a diagnostic: how many households a careless reading ("they gave us their email, they said yes to emails") would have admitted.
with params as (

    select
        lower(max(case when param = 'activation_requires_timestamp' then value end)) = 'true' as need_when,
        lower(max(case when param = 'activation_requires_wording' then value end)) = 'true' as need_which
    from {{ ref('p5_params') }}

),

h as (select distinct household_id from {{ ref('p5_household') }}),

mk as (select * from {{ ref('p5_household_purpose_status') }} where purpose = 'NFL_CLUB_MARKETING'),

comms as (select * from {{ ref('p5_household_purpose_status') }} where purpose = 'LEAGUE_COMMUNICATIONS' and status = 'GRANTED')

select
    h.household_id,
    mk.status is not null                                                   as has_marketing_event,
    mk.status = 'GRANTED'                                                   as marketing_granted,
    coalesce(mk.provenance_known, false)                                    as marketing_provenance_known,
    mk.status = 'GRANTED' and (not p.need_when or mk.when_known) and (not p.need_which or mk.which_known) as eligible_for_club_activation,
    case when mk.status is null then 'NO_MARKETING_OPT_IN_CAPTURED'
         when mk.status = 'DENIED' then 'MARKETING_DECLINED'
         when p.need_when and not mk.when_known then 'GRANTED_BUT_NO_TIMESTAMP'
         when p.need_which and not mk.which_known then 'GRANTED_BUT_WORDING_UNKNOWN'
         else 'ELIGIBLE' end                                                as activation_status,
    comms.household_id is not null                                         as league_comms_granted
from h cross join params p
left join mk on mk.household_id = h.household_id
left join comms on comms.household_id = h.household_id
