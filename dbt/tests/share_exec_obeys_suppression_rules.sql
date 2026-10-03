{{ config(tags=['phase3']) }}
-- Every share_exec table obeys the small-cell rules, checked independently of the suppress_small_cells macro:
-- no count above zero and below k_min is published (primary), and no group of sibling cells with a published subtotal
-- has exactly one suppressed cell (secondary).
select 'global' as share, * from {{ suppression_group_violations(ref('share_exec__participation_global'), ['participation_year'], 'unique_participants') }}
union all
select 'status', * from {{ suppression_group_violations(ref('share_exec__participation_status'), ['participation_year', 'status'], 'participants') }}
union all
select 'by_country', * from {{ suppression_group_violations(ref('share_exec__participation_by_country'), ['participation_year', 'country_code'], 'participants_attributed') }}
union all
select 'segments', * from {{ suppression_group_violations(ref('share_exec__participation_segments'), ['participation_year', 'country_code', 'age_band'], 'participants') }}
union all
select 'by_sex', * from {{ suppression_group_violations(ref('share_exec__participation_by_sex'), ['participation_year', 'sex'], 'participants') }}
union all
select 'fan_funnel', * from {{ suppression_group_violations(ref('share_exec__fan_funnel'), ['cohort_year', 'segment', 'fan_status'], 'funnel_households') }}
union all
select 'addressable_audience', * from {{ suppression_group_violations(ref('share_exec__addressable_audience'), ['month', 'household_group'], 'audience_registered') }}
union all
select 'fan_value', * from {{ suppression_group_violations(ref('share_exec__fan_value'), ['fan_group'], 'value_accounts') }}
union all
select 'fan_rfm', * from {{ suppression_group_violations(ref('share_exec__fan_rfm'), ['year', 'fan_group', 'segment'], 'rfm_accounts') }}
union all
select 'fan_survival', * from {{ suppression_group_violations(ref('share_exec__fan_survival'), ['fan_group', 'months_since_origin'], 'survival_at_risk') }}
union all
select 'fan_value_uplift', * from {{ suppression_group_violations(ref('share_exec__fan_value_uplift'), ['uplift_status_group', 'uplift_outcome'], 'uplift_households') }}
union all
select 'consent_capture', * from {{ suppression_group_violations(ref('share_exec__consent_capture'), ['consent_cut', 'consent_dimension_value', 'consent_channel'], 'consent_lines') }}
