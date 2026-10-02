-- MARKETING share: a contact list, one row per contact email, under strict rules:
--   * the email is included ONLY if EVERY participant who shares it has consent_marketing = TRUE. NULL is not consent and
--     any FALSE or NULL among siblings who share a guardian email excludes the address (a guardian's choice for one
--     child is not assumed for the others)
--   * participants in a cluster with an open integrity issue are excluded: their consent may belong to someone else
--   * a minor's own details are NEVER included: for a minor the contact IS the guardian (the registration's contact),
--     the row carries no child name, date of birth or any child attribute
--   * contact_first_name is filled only when the address belongs to exactly one participant who is an adult
with p as (

    select participant_id, contact_email, is_minor_current, first_name, home_country_code,
           consent_marketing, consent_marketing_captured_at, consent_marketing_season_year, last_season,
           has_open_integrity_issue
    from {{ ref('dim_participant') }}
    where contact_email is not null

),

by_email as (

    select
        contact_email,
        count(*)                                                            as participants,
        count(*) filter (where consent_marketing is true)                   as consented,
        bool_or(has_open_integrity_issue)                                   as any_open_issue,
        bool_or(is_minor_current is not false)                              as any_minor_or_unknown,
        max(first_name) filter (where is_minor_current is false)            as adult_first_name,
        max(consent_marketing_captured_at)                                  as consent_marketing_captured_at,
        max(consent_marketing_season_year)                                  as consent_marketing_season_year,
        (array_agg(home_country_code order by last_season desc, participant_id))[1] as country_code
    from p
    group by contact_email

)

select
    contact_email,
    case when any_minor_or_unknown then 'GUARDIAN_OF_MINOR' else 'ADULT_PLAYER' end as contact_role,
    case when participants = 1 and not any_minor_or_unknown then adult_first_name end as contact_first_name,
    country_code,
    true                                                                    as consent_marketing,
    consent_marketing_captured_at,
    consent_marketing_season_year
from by_email
where consented = participants and not any_open_issue
