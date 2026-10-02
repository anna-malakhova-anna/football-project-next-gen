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
