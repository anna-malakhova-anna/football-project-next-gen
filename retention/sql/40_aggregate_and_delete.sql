-- Keep only aggregates of what is about to go (counts by reason, market and age band), then delete the child-level rows, then the parent side of any household left with no child.
insert into pii_store.retained_aggregate
select '{run_id}', reason, market_id, age_band, count(distinct p5_person_id), count(*) from _due_records group by 1, 2, 3, 4;
create or replace temp table _purged_households as
select distinct household_id from pii_store.child_record where household_id is not null
except
select distinct r.household_id from pii_store.child_record r where (r.feed, r.source_record_id) not in (select (feed, source_record_id) from _due_records) and r.household_id is not null;
delete from pii_store.child_record where (feed, source_record_id) in (select (feed, source_record_id) from _due_records);
insert into pii_store.suppression_list select parent_email_hash, revoked_at, '{run_id}' from pii_store.revocation where household_id in (select household_id from _purged_households);
delete from pii_store.consent_event where household_id in (select household_id from _purged_households);
delete from pii_store.household_activation where household_id in (select household_id from _purged_households);
delete from pii_store.household_contact where household_id in (select household_id from _purged_households);
delete from pii_store.revocation where household_id in (select household_id from _purged_households)
