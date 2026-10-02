-- ANALYST share: participant-year grain for analysis and modelling. NO names, contact details or DOB:
--   analyst_key   sha256(participant_id || salt), salt from FLAG_PSEUDO_SALT (macro pseudonymize)
--   birth_year    the year only, never the date of birth
--   postal_prefix the first privacy_params.postal_prefix_len characters of the latest postal code (US ZIP3, CA FSA)
-- Organization ids are left out on purpose (organization + birth year + postal prefix + sex narrows small leagues).
-- Pseudonymized data is still personal data; see ADR-006 for the k-anonymity risk and the measured smallest class.
with latest_postal as (

    select participant_id, left(postal_code, {{ privacy_param('postal_prefix_len') }}) as postal_prefix
    from (
        select b.participant_id, i.postal_code,
               row_number() over (partition by b.participant_id
                                  order by i.season_year desc, {{ term_order('i.season_term') }} desc, i.registered_at desc nulls last, i.match_record_id) as rn
        from {{ ref('bridge_registration_participant') }} b
        join {{ ref('idr_input_records') }} i on i.match_record_id = b.match_record_id
        where b.registration_key = b.match_record_id and i.postal_code is not null
    ) where rn = 1

)

select
    {{ pseudonymize('f.participant_id') }}                                  as analyst_key,
    f.participation_year,
    f.valid_registration_count,
    f.org_count,
    f.is_multi_org,
    f.attributed_country_code,
    f.countries_played,
    d.birth_year,
    f.age_band,
    f.is_youth,
    f.primary_division,
    f.sex,
    p.postal_prefix,
    f.status,
    f.resolution_confidence,
    f.has_open_integrity_issue
from {{ ref('fct_participant_year') }} f
join {{ ref('dim_participant') }} d on d.participant_id = f.participant_id
left join latest_postal p on p.participant_id = f.participant_id
