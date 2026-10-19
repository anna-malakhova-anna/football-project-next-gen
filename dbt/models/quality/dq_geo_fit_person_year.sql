-- DP1 RESTRICTED PORT (consumer: DP4). Per participant and season: how many of their registrations are fit for the GEO purpose. A person key and two counts; no organization, record key
-- or contact field. Club-market coverage weights these counts by the participant's market allocation (a DP2 fact DP1 does not hold), so this cannot be published as an aggregate.
select person_id as participant_id, season_year as participation_year, count(*) as records, count(*) filter (where fit_for_geo) as records_fit_for_geo
from {{ ref('dq_record_fitness') }}
where source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED')
group by 1, 2
