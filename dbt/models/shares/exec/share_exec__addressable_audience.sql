{{ config(tags=['phase4']) }}
-- EXEC share: the addressable audience and the consent gap by month and household group (NULL group = all registered households). COUNTS ONLY: how many households are registered, linked to a
-- fan account, contactable on at least one channel (guardian opt-in; no record is not "no"), and how many ACTIVE households have no opt-in at all (the consent gap). No list, no identifier, never a
-- marketing audience (ADR-009). The gap value is SYNTHETIC CURRENCY and ILLUSTRATIVE. Small cells suppressed.
with src as (

    select month, household_group,
           households_registered     as audience_registered,
           linked_households         as audience_linked,
           contactable_households    as audience_contactable,
           contactable_email         as audience_contactable_email,
           contactable_sms           as audience_contactable_sms,
           contactable_push          as audience_contactable_push,
           active_households         as audience_active,
           consent_gap_households    as consent_gap_households,
           contactable_share_of_linked as contactable_share_of_linked,
           consent_gap_share_of_active as consent_gap_share_of_active,
           consent_gap_value         as consent_gap_value
    from {{ ref('mart_addressable_audience') }}
    where household_group <> 'ALL'
    union all
    select month, cast(null as varchar), households_registered, linked_households, contactable_households, contactable_email, contactable_sms, contactable_push,
           active_households, consent_gap_households, contactable_share_of_linked, consent_gap_share_of_active, consent_gap_value
    from {{ ref('mart_addressable_audience') }}
    where household_group = 'ALL'

)

select month, household_group, audience_registered, audience_linked, audience_contactable, audience_contactable_email, audience_contactable_sms, audience_contactable_push,
       audience_active, consent_gap_households, contactable_share_of_linked, consent_gap_share_of_active, consent_gap_value, suppressed
from {{ suppress_small_cells('src', ['month', 'household_group'],
        ['audience_registered', 'audience_linked', 'audience_contactable', 'audience_contactable_email', 'audience_contactable_sms', 'audience_contactable_push', 'audience_active', 'consent_gap_households'],
        rates={'contactable_share_of_linked': ['audience_linked', 'audience_contactable'], 'consent_gap_share_of_active': ['audience_active', 'consent_gap_households'],
               'consent_gap_value': ['consent_gap_households']}) }}
order by month, household_group nulls first
