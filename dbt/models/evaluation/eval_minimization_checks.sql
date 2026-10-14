{{ config(tags=['phase5']) }}
-- depends_on: {{ ref('eval_pairwise') }}
-- GROUND TRUTH (evaluation only). Pass/fail checks on the minimization frontier. Each row is one claim; a failing claim is a finding to report, not a threshold to tune.
{% set runs = adapter.get_relation(database=target.database, schema='eval', identifier='minimization_runs') %}
with t as (select * from {{ ref('eval_minimization_tradeoff') }}),

seed as (select count(*) as n from {{ ref('minimization_variants') }})

{% if runs is none %}
select 'minimization_runs_exist' as check_name, false as passed, 'run make minimize' as detail
{% else %}
select 'every_variant_has_both_matchers' as check_name,
       (select count(*) from t where matcher is not null) = 2 * (select n from seed) as passed,
       'rows: ' || (select count(*) from t where matcher is not null) || ' of ' || 2 * (select n from seed) as detail
union all
select 'full_variant_matches_the_default_build',
       coalesce((select bool_and(abs(t.precision - p.precision) < 1e-9 and abs(t.recall - p.recall) < 1e-9)
                 from t join {{ ref('eval_pairwise') }} p on p.matcher = t.matcher and p.stage = 'PRE_REVIEW' and p.scope = 'AUTO'
                 where t.variant_id = 'V0_FULL'), false),
       'V0_FULL run against the default evaluation: the macro changes nothing when no coarsening is asked for'
union all
select 'risk_never_rises_as_fields_are_coarsened',
       coalesce((select bool_and(pct_unique <= prev) from (select pct_unique, lag(pct_unique) over (order by sort_order) as prev from (select distinct sort_order, pct_unique from t)) where prev is not null), false),
       'share of participant-years that are unique, by variant order'
union all
select 'hashed_contact_cannot_activate',
       coalesce((select bool_and(fit_for_activate = 0) from t where variant_id = 'V4_HASHED_CONTACT'), false),
       'a hashed email reaches no guardian'
{% endif %}
