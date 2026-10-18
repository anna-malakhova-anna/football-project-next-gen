{{ config(tags=['phase6']) }}
-- PRIVACY share: the numbers inside headline sentences on the privacy page (Phase 5.1, section 5.2), computed and rounded here. Long format as share_club__chart_insights.
-- Reads other share_privacy models and share_exec__roadmap_gates (all already aggregated); shares are whole percents.
with
prov as (
    select sum(consent_events) as total, sum(consent_events) filter (where provenance_grade = 'KNOWN_FULL') as full_known
    from {{ ref('share_privacy__consent_provenance') }}
    where participation_year = (select max(participation_year) from {{ ref('share_privacy__consent_provenance') }} where source_system is not null)
      and source_system is not null and suppressed = 'NONE'
),

cover as (
    select count(distinct consent_text_version) as versions,
           count(distinct consent_text_version) filter (where counts_for_club_activation and form_names_purpose) as versions_ok
    from {{ ref('share_privacy__purpose_coverage') }}
),

frontier as (
    select f.variant_id, f.pct_unique, f.fit_for_count, v.in_standard
    from {{ ref('share_privacy__minimization_frontier') }} f
    join {{ ref('minimization_variants') }} v using (variant_id)
),

ret as (
    select count(*) as metrics, count(*) filter (where survives_facts_only) as kept_facts, count(*) filter (where survives_identity_rebuilt) as kept_rebuilt
    from {{ ref('share_privacy__retention_vs_deletion') }}
),

kanon as (
    select pct_unique from {{ ref('share_privacy__analyst_k_anonymity') }} order by participation_year desc limit 1
),

prio as (
    select product_id, value_to_goals + feasibility_today + data_readiness - privacy_risk as total from {{ ref('product_prioritization') }}
),

goals as (select count(distinct goal_id) as n_goals, count(distinct product_id) as n_goal_products, count(distinct kpi_id) as n_kpis,
                 count(distinct kpi_id) filter (where status = 'NOT_MEASURABLE_BY_DESIGN') as n_not_measurable from {{ ref('mart_goal_scorecard') }}),

rules as (select count(*) as n_rows, count(*) filter (where verified <> 'Y') as n_unverified, count(*) filter (where age_max < 18) as n_minor_rows,
                 count(*) filter (where age_max < 18 and who_consents = 'GUARDIAN') as n_minor_guardian_rows from {{ ref('age_consent_rules') }}),

tier as (select age_tier, share_of_registered from {{ ref('mart_conversion_funnel_by_tier') }} where step_no = 5),

rows_ as (
    select 'P1' as chart_id, 'privacy' as lens, 'pct_provenance_full' as field, cast(round(100.0 * full_known / nullif(total, 0)) as bigint) || '%' as value_display, round(100.0 * full_known / nullif(total, 0)) as value_raw from prov
    union all select 'P2', 'privacy', 'n_versions', cast(versions as varchar), versions * 1.0 from cover
    union all select 'P2', 'privacy', 'n_versions_ok', cast(versions_ok as varchar), versions_ok * 1.0 from cover
    union all select 'P3', 'privacy', 'pct_unique_v0', cast(round(pct_unique) as bigint) || '%', round(pct_unique) from frontier where variant_id = (select min(variant_id) from frontier)
    union all select 'P3', 'privacy', 'pct_unique_standard', cast(round(pct_unique) as bigint) || '%', round(pct_unique) from frontier where in_standard
    union all select 'P3', 'privacy', 'fit_count_standard', cast(round(100 * fit_for_count) as bigint) || '%', round(100 * fit_for_count) from frontier where in_standard
    union all select 'P4', 'privacy', 'n_metrics', cast(metrics as varchar), metrics * 1.0 from ret
    union all select 'P4', 'privacy', 'n_metrics_kept_facts', cast(kept_facts as varchar), kept_facts * 1.0 from ret
    union all select 'P4', 'privacy', 'n_metrics_kept_rebuilt', cast(kept_rebuilt as varchar), kept_rebuilt * 1.0 from ret
    union all select 'P5', 'privacy', 'pct_unique_analyst_share', cast(round(pct_unique) as bigint) || '%', round(pct_unique) from kanon
    union all select 'D1', 'both', 'n_products', cast(count(*) as varchar), count(*) * 1.0 from prio
    union all select 'D1', 'both', 'n_goals', cast(n_goals as varchar), n_goals * 1.0 from goals
    union all select 'D4', 'both', 'priority_dp1', cast(total as varchar), total * 1.0 from prio where product_id = 'DP1'
    union all select 'D4', 'both', 'priority_dp4', cast(total as varchar), total * 1.0 from prio where product_id = 'DP4'
    union all select 'D4', 'both', 'priority_dp5', cast(total as varchar), total * 1.0 from prio where product_id = 'DP5'
    union all select 'D4', 'both', 'priority_max', cast(max(total) as varchar), max(total) * 1.0 from prio
    union all select 'D10', 'both', 'n_met', cast(n_met as varchar), n_met * 1.0 from (select distinct n_met from {{ ref('share_exec__roadmap_gates') }})
    union all select 'D10', 'both', 'n_gates', cast(n_gates as varchar), n_gates * 1.0 from (select distinct n_gates from {{ ref('share_exec__roadmap_gates') }})
    union all select 'D10', 'both', 'blocking_gate_plain', blocking_gate_plain, cast(null as double) from (select distinct blocking_gate_plain from {{ ref('share_exec__roadmap_gates') }})
    union all select 'D6', 'privacy', 'n_minor_rows', cast(n_minor_rows as varchar), n_minor_rows * 1.0 from rules
    union all select 'D6', 'privacy', 'n_minor_guardian_rows', cast(n_minor_guardian_rows as varchar), n_minor_guardian_rows * 1.0 from rules
    union all select 'D6', 'privacy', 'n_unverified_rules', cast(n_unverified as varchar), n_unverified * 1.0 from rules
    union all select 'D6', 'privacy', 'n_rule_rows', cast(n_rows as varchar), n_rows * 1.0 from rules
    union all select 'D6', 'privacy', 'pct_activatable_u13', cast(round(100 * share_of_registered) as bigint) || '%', round(100 * share_of_registered) from tier where age_tier = 'U13'
    union all select 'D6', 'privacy', 'pct_activatable_adult', cast(round(100 * share_of_registered) as bigint) || '%', round(100 * share_of_registered) from tier where age_tier = 'ADULT'
    union all select 'D7', 'both', 'n_kpis', cast(n_kpis as varchar), n_kpis * 1.0 from goals
    union all select 'D7', 'both', 'n_not_measurable', cast(n_not_measurable as varchar), n_not_measurable * 1.0 from goals
)

select chart_id, lens, field, value_display, value_raw, 'NONE' as suppressed
from rows_
order by chart_id, field
