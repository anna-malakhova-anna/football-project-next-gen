-- DP1 AGGREGATE PORT. Per season: how many distinct participants have at least one registration fit for the COUNT purpose (the strict side of the DQ-exclusion component).
-- Counts only: no person, organization or record key leaves DP1. Read by mart_uncertainty_decomposition (DP3) instead of the record-level dq_record_fitness.
select season_year, count(distinct person_id) as participants_fit_for_count
from {{ ref('dq_record_fitness') }}
where fit_for_count and source_system in ('US_LEAGUE', 'CA_CLUB', 'INTL_FED')
group by 1
