{{ config(tags=['phase4']) }}
-- Every source that has reached Contracted or beyond has a contract that was validated: no source is staged, modelled or in
-- production on trust. (Sources still in Discovery or Profiling have no contract yet.)
select r.source_system, r.onboarding_status
from {{ ref('source_registry') }} r
left join (select distinct source_system from {{ source('contracts', 'dq_contract_results') }}) c using (source_system)
where r.onboarding_status in ('Contracted', 'Staged', 'Modelled', 'Production') and c.source_system is null
