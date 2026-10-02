-- Cross-reference: participant -> source system -> identifier -> where and when it was seen.
-- One row per distinct identifier per participant: source person ids (CA member UUIDs, INTL Player IDs) and the
-- contact emails seen. Identifiers are direct identifiers; Phase 3 views must mask them.
with b as (

    select participant_id, match_record_id from {{ ref('bridge_registration_participant') }}
    where registration_key = match_record_id

),

r as (

    select b.participant_id, i.source_system, i.source_person_id, i.contact_email, i.season_year, i.country_code
    from b join {{ ref('idr_input_records') }} i using (match_record_id)

)

select participant_id, source_system, 'SOURCE_PERSON_ID' as identifier_type,
       case when source_system = 'INTL_FED' then country_code || '|' || source_person_id else source_person_id end as identifier_value,
       min(season_year) as first_seen_season, max(season_year) as last_seen_season, count(*) as registration_count
from r where source_person_id is not null
group by 1, 2, 3, 4
union all
select participant_id, source_system, 'CONTACT_EMAIL', contact_email, min(season_year), max(season_year), count(*)
from r where contact_email is not null
group by 1, 2, 3, 4
