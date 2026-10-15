{{ config(tags=['phase5']) }}
-- PRIVACY share: the numbers inside headline sentences on the privacy page (Phase 5.1, section 5.2), computed and rounded here. Long format as share_club__chart_insights.
-- Reads other share_privacy models only (already aggregated and suppressed); shares are whole percents.
with
prov as (
    select sum(consent_events) as total, sum(consent_events) filter (where provenance_grade = 'KNOWN_FULL') as full_known
    from {{ ref('share_privacy__consent_provenance') }}
    where participation_year = (select max(participation_year) from {{ ref('share_privacy__consent_provenance') }} where source_system is not null)
      and source_system is not null and suppressed = 'NONE'
),

cover as (
    select count(distinct consent_text_version) as versions,
           count(distinct consent_text_version) filter (where counts_for_club_activation) as versions_ok
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
)

select chart_id, lens, field, value_display, value_raw, 'NONE' as suppressed
from rows_
order by chart_id, field
