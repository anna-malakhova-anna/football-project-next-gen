{{ config(tags=['phase3']) }}
-- Every data-quality flag raised in the unioned model must be classified in the dq_flag_severity seed, so the
-- "registrations failing DQ rules" KPI cannot silently ignore a new flag.
select distinct f.flag
from (select unnest(dq_flags) as flag from {{ ref('int_registrations_unioned') }}) f
left join {{ ref('dq_flag_severity') }} s using (flag)
where s.flag is null
