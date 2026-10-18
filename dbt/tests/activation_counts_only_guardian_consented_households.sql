{{ config(tags=['phase6']) }}
-- Phase 6 (ADR-022). The activation step of the conversion funnel counts exactly the households whose guardian's CLUB_MARKETING permission is Y, per age tier, and no household whose youngest child
-- is a minor is counted without a guardian consent on record with full provenance (project policy: guardian consent for ALL minors, 13 to 17 included). The funnel is nested for steps 2 to 4 and
-- carries no household, participant, child or contact column.
with c as (

    select governing_tier as age_tier, count(*) as n from {{ ref('int_consent_permissions') }} where purpose = 'CLUB_MARKETING' and permitted = 'Y' group by 1

)

select f.age_tier || '|' || f.step_no as detail, 'activation step differs from the permitted households' as problem
from {{ ref('mart_conversion_funnel_by_tier') }} f left join c on c.age_tier = f.age_tier
where f.step_no = 5 and f.households is not null and f.households <> coalesce(c.n, 0)
union all
select household_id, 'a minor household counted as activatable without a full guardian consent'
from {{ ref('int_consent_permissions') }}
where purpose = 'CLUB_MARKETING' and permitted = 'Y' and governing_tier in ('U13', '13_15', '16_17', 'UNKNOWN') and (consent_status <> 'GRANTED_FULL' or who_consents <> 'GUARDIAN')
union all
select table_name || '.' || column_name, 'identifying column in a Phase 6 funnel or permission model'
from information_schema.columns
where table_schema in ('{{ ref("mart_conversion_funnel_by_tier").schema }}', '{{ ref("int_consent_permissions").schema }}')
  and table_name in ('mart_conversion_funnel_by_tier', 'int_consent_permissions')
  and regexp_matches(lower(column_name), 'participant|person|child|first_name|last_name|birth|dob|email|phone|registration_key|source_record|record_key|age_at')
union all
select age_tier || '|' || step_no, 'funnel not nested'
from (select a.age_tier, a.step_no from {{ ref('mart_conversion_funnel_by_tier') }} a join {{ ref('mart_conversion_funnel_by_tier') }} b on a.age_tier = b.age_tier and b.step_no = a.step_no - 1
      where a.step_no between 2 and 4 and a.households is not null and b.households is not null and a.households > b.households)
