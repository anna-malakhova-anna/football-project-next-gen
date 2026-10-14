{{ config(schema='phase5') }}
-- AGGREGATE. Consent provenance by feed: how many events, and how many know WHAT, WHEN and WHICH WORDING; the average provenance score (0 to 3).
select
    source_feed,
    event_kind,
    count(*)                                                                as events,
    round(avg(what_known::integer), 4)                                      as share_what_known,
    round(avg(when_known::integer), 4)                                      as share_when_known,
    round(avg(which_known::integer), 4)                                     as share_which_known,
    round(avg(provenance_score), 3)                                         as avg_provenance_score,
    round(avg(provenance_known::integer), 4)                                as share_fully_known,
    count(*) filter (where household_id is null)                            as events_with_no_household
from {{ ref('p5_consent_event') }}
group by 1, 2
