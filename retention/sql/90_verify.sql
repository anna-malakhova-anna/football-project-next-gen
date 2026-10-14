-- Independent invariant checks, written without the plan tables. Each query returns the violations it finds; the job passes only if all are empty.
-- v1 no child-level record of an aged-out child survives
select 'v1 aged-out child survives' as check_name, count(distinct p5_person_id) as violations from (
    select p5_person_id, min(birth_year) filter (where birth_year >= 1900) as ref_by from pii_store.child_record group by 1
) where ref_by is not null and cast(make_date(ref_by + {age_out_age}, 12, 31) + to_months({grace_months}) as date) <= cast('{as_of}' as date);
-- v2 no registration older than the maximum record age survives
select 'v2 record older than the cap survives', count(*) from pii_store.child_record where cast(registered_at as date) + to_months({max_record_months}) <= cast('{as_of}' as date);
-- v3 no child of a household that revoked (and whose delay has passed) survives
select 'v3 revoked household child data survives', count(*) from pii_store.child_record c
where c.household_id in (select household_id from pii_store.revocation where cast(revoked_at as date) + {revocation_delay_days} <= cast('{as_of}' as date));
-- v4 no revoked household is activation-eligible
select 'v4 revoked household still eligible', count(*) from pii_store.household_activation a
where a.eligible_for_club_activation and a.household_id in (select household_id from pii_store.revocation where revoked_at <= cast('{as_of}' as date) + interval 1 day - interval 1 second);
-- v5 no parent-side row survives for a household with no child record
select 'v5 orphan parent data survives', (
    (select count(*) from pii_store.household_contact where household_id not in (select household_id from pii_store.child_record where household_id is not null))
  + (select count(*) from pii_store.consent_event where household_id not in (select household_id from pii_store.child_record where household_id is not null))
  + (select count(*) from pii_store.household_activation where household_id not in (select household_id from pii_store.child_record where household_id is not null))
);
-- v6 the log and the aggregates hold no identifying column
select 'v6 identifying column in log or aggregate', count(*) from information_schema.columns
where table_schema = 'pii_store' and table_name in ('retention_log', 'retained_aggregate')
  and column_name <> 'table_name' and regexp_matches(lower(column_name), 'name|email|birth|dob|zip|person|household_id|record_id|source_record')
