{{ config(tags=['phase5']) }}
-- The child entity is never joined to activation outputs (spec section 8; extends the Phase 3 marketing-share test). The funnel and its loss table are counts: no identifier of a participant, a household,
-- a registration or a person, and no name, birth or contact column. The household-level consent models are keyed by household only and carry no participant column. The funnel is nested and its loss
-- splits add up (counts are allocated, so fractional: compared to 1e-6).
select table_name || '.' || column_name as detail, 'identifying column in an activation output' as problem
from information_schema.columns
where table_schema in ('{{ ref("mart_activation_funnel").schema }}', '{{ ref("int_household_year_consent").schema }}')
  and table_name in ('mart_activation_funnel', 'mart_activation_funnel_loss', 'int_household_year_consent')
  and regexp_matches(lower(column_name), 'participant|person|child|first_name|last_name|birth|dob|email|phone|registration_key|source_record|record_key') and lower(column_name) not in ('participation_year')
union all
select market_id || '|' || participation_year, 'funnel not nested'
from (select market_id, participation_year, max(n) filter (where step_no = 3) as h3, max(n) filter (where step_no = 4) as h4, max(n) filter (where step_no = 5) as h5, max(n) filter (where step_no = 6) as h6
      from {{ ref('mart_activation_funnel') }} group by all) where h4 > h3 + 1e-6 or h5 > h4 + 1e-6 or h6 > h5 + 1e-6
union all
select market_id || '|' || participation_year || '|' || step_no, 'loss split does not add up'
from {{ ref('mart_activation_funnel') }} where step_no > 1 and abs(lost - (lost_unit + lost_dq + lost_privacy)) > 1e-6
union all
select market_id || '|' || participation_year, 'loss reasons do not add up to households'
from (select f.market_id, f.participation_year, max(f.n) filter (where f.step_no = 3) as h, (select sum(l.households) from {{ ref('mart_activation_funnel_loss') }} l where l.market_id = f.market_id and l.participation_year = f.participation_year) as s
      from {{ ref('mart_activation_funnel') }} f group by all) where abs(h - s) > 1e-6
