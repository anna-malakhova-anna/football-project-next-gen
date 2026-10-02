{{ config(tags=['phase3']) }}
-- Independent re-derivation of who may be contacted, from dim_participant (not from the share's own logic):
--   * every address in the share: ALL participants sharing it have marketing consent TRUE (NULL and FALSE are not
--     consent), none in a cluster with an open integrity issue
--   * every address that qualifies IS in the share (completeness)
--   * the share never carries a minor's own details: no child name (contact_first_name is NULL for guardians and never
--     equals the first name of a minor who shares the address), and none of the forbidden columns exists
with eligible as (

    select contact_email
    from {{ ref('dim_participant') }}
    where contact_email is not null
    group by contact_email
    having count(*) = count(*) filter (where consent_marketing is true) and not bool_or(has_open_integrity_issue)

)
select 'address_without_full_consent' as problem, s.contact_email as detail
from {{ ref('share_marketing__contact_list') }} s left join eligible e using (contact_email) where e.contact_email is null
union all
select 'eligible_address_missing', e.contact_email
from eligible e left join {{ ref('share_marketing__contact_list') }} s using (contact_email) where s.contact_email is null
union all
select 'consent_flag_not_true', contact_email from {{ ref('share_marketing__contact_list') }} where consent_marketing is not true
union all
select 'guardian_row_carries_a_name', contact_email from {{ ref('share_marketing__contact_list') }}
where contact_role = 'GUARDIAN_OF_MINOR' and contact_first_name is not null
union all
select 'name_matches_a_minor_sharing_the_address', s.contact_email
from {{ ref('share_marketing__contact_list') }} s
join {{ ref('dim_participant') }} d on d.contact_email = s.contact_email and d.is_minor_current is not false
where s.contact_first_name is not null and lower(s.contact_first_name) = lower(d.first_name)
union all
select 'forbidden_column', column_name from information_schema.columns
where table_schema = 'share_marketing'
  and (lower(column_name) in ('last_name', 'first_name', 'dob', 'birth_year', 'sex', 'participant_id', 'contact_phone', 'postal_code')
       or lower(column_name) like '%dob%' or lower(column_name) like 'consent_photo%')
