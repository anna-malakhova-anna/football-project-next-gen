{{ config(tags=['phase5']) }}
-- One fitness row per registration of the modelled sources and channel feeds, and fitness agrees with the failing-rule lists: fit means the list for that purpose is empty.
-- A record that fails a rule listing a purpose is never fit for it (re-derived here from the registry for the exact-duplicate rule, an ERROR rule for COUNT).
select 'row count differs from the registrations' as problem
where (select count(*) from {{ ref('dq_record_fitness') }}) <>
      (select count(*) from {{ ref('dq_record_resolved') }} where person_id is not null)
union all
select distinct 'fit_for_count disagrees with its failing rules' from {{ ref('dq_record_fitness') }} where fit_for_count <> (len(failing_rules_count) = 0)
union all
select distinct 'fit_for_activate disagrees with its failing rules' from {{ ref('dq_record_fitness') }} where fit_for_activate <> (len(failing_rules_activate) = 0)
union all
select distinct 'exact duplicate is fit for COUNT' from {{ ref('dq_record_fitness') }} f join {{ ref('dq_record_base') }} b using (record_key)
where list_contains(b.dq_flags, 'exact_duplicate') and f.fit_for_count
union all
select distinct 'failing rule not in the registry' from (select unnest(failing_rules_activate) as rule_id from {{ ref('dq_record_fitness') }})
where rule_id not in (select rule_id from {{ ref('dq_rule_registry') }})
