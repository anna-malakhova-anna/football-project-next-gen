{{ config(tags=['phase5']) }}
-- No marketing join ever touches the child entity. The household consent chain (events, purpose status, activation) and the aggregates built on it must carry no child
-- identifier, child name, birth year or record id that could be joined back to a child. p5_consent_event keeps source_record_id for audit, but it is an event table,
-- not an activation table; everything the activation decision and the club-facing funnel read downstream of it is checked here.
select table_name, column_name
from information_schema.columns
where table_schema in ('phase5', 'phase5_restricted')
  and table_name in ('p5_household_purpose_status', 'p5_household_activation', 'p5_consent_funnel', 'p5_purpose_limitation', 'p5_consent_provenance_by_feed')
  and regexp_matches(lower(column_name), 'person|child|first_name|last_name|given|family|birth|dob|record_id|source_record')
