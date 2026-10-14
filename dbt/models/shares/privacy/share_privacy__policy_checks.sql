{{ config(tags=['phase5']) }}
-- PRIVACY share: results of the share-policy check (scripts/check_share_policy.py), one row per check kind with the number of violations found on its last run. The script writes
-- audit_share_policy.policy_check_results; this model tolerates the table being missing (empty until the check has run). Counts only.
{% set rel = adapter.get_relation(database=target.database, schema='audit_share_policy', identifier='policy_check_results') %}
{% if rel is not none %}
select check_name, violations, columns_checked, share_tables_checked from {{ source('audit_share_policy', 'policy_check_results') }} order by check_name
{% else %}
select cast(null as varchar) as check_name, cast(null as integer) as violations, cast(null as integer) as columns_checked, cast(null as integer) as share_tables_checked where false
{% endif %}
