{{ config(schema='phase5') }}
-- AGGREGATE. What purpose limitation does: households a careless reading would have admitted to club activation, and why they are not.
-- Careless reading = "the parent gave us their email and agreed to league emails, so we may market to them". The NFL FLAG notice (public source) says emails collected for parental
-- consent are not used for marketing unless the parent separately opted in; the design here follows that.
select
    count(*)                                                                as households,
    count(*) filter (where league_comms_granted)                            as league_comms_granted,
    count(*) filter (where eligible_for_club_activation)                    as eligible_for_club_activation,
    count(*) filter (where league_comms_granted and not eligible_for_club_activation) as admitted_only_by_a_careless_reading,
    round(count(*) filter (where league_comms_granted and not eligible_for_club_activation)::double / nullif(count(*) filter (where league_comms_granted), 0), 4) as share_of_comms_households_blocked
from {{ ref('p5_household_activation') }}
