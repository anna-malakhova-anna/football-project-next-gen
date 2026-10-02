{{ config(tags=['phase4']) }}
-- Contract validation (scripts/validate_contracts.py) must have run and must hold no ERROR: a missing consent column, a consent
-- value the contract does not allow, a missing required PII column, an undeclared raw column. WARN rows are reported, not failed.
select source_system, rule, column_name, observed, threshold, detail
from {{ source('contracts', 'dq_contract_results') }}
where status = 'ERROR'
union all
select 'ALL', 'no_contract_results_found', null, null, null, 'run `make contracts` first'
where (select count(*) from {{ source('contracts', 'dq_contract_results') }}) = 0
