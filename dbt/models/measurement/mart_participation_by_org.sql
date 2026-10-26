-- Participants by year and organization (Phase 7, ADR-025 section 2): DP3's aggregate port for like-for-like growth. A person is counted in every
-- organization they hold a valid registration with that year (NON-ADDITIVE across organizations, like participants_present across countries).
-- Organization level only: no person data leaves; audiences see growth labels built on it, never these counts.
select
    participation_year,
    organization_id                                                         as org_id,
    source_system,
    country_code,
    count(distinct participant_id)                                          as participants,
    '{{ var("methodology_version") }}'                                      as methodology_version
from {{ ref('fct_registration') }}
where is_valid_registration and organization_id is not null
group by 1, 2, 3, 4
order by 1, 2
