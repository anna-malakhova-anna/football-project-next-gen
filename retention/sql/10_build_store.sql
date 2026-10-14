-- Rebuild the store from the dbt models of Phase 5 (a fresh copy every time, so a job run is repeatable). Runs inside the warehouse that dbt built.
create or replace table pii_store.child_record as
select
    rp.feed, rp.source_record_id, rp.p5_person_id, h.household_id,
    s.first_name, s.last_name, s.birth_year, s.sex, s.postal_code as zip5, rp.contact_email as parent_email,
    coalesce(c.market_id, 'UNKNOWN') as market_id, coalesce(c.age_band, 'UNKNOWN') as age_band, rp.season_year, rp.registered_at
from phase5_restricted.p5_record_person rp
join phase5.stg_p5_registrations s on s.feed = rp.feed and s.source_record_id = rp.source_record_id
left join phase5_restricted.p5_household h on h.contact_email = rp.contact_email
left join phase5_restricted.p5_child c on c.p5_person_id = rp.p5_person_id;
create or replace table pii_store.household_contact as
select household_id, contact_email as parent_email from phase5_restricted.p5_household;
create or replace table pii_store.consent_event as
select consent_event_id, household_id, event_kind, status, array_to_string(purposes, '|') as purposes, event_ts, registered_at
from phase5_restricted.p5_consent_event where household_id is not null;
create or replace table pii_store.household_activation as
select household_id, eligible_for_club_activation, activation_status from phase5_restricted.p5_household_activation;
create or replace table pii_store.revocation as
select h.household_id, sha256(lower(trim(r.parent_email))) as parent_email_hash, try_cast(r.revoked_at as timestamp) as revoked_at
from raw.p5_revocations r join phase5_restricted.p5_household h on h.contact_email = lower(trim(r.parent_email));
create or replace table pii_store.suppression_list (parent_email_hash varchar, revoked_at timestamp, run_id varchar);
create or replace table pii_store.retained_aggregate (run_id varchar, reason varchar, market_id varchar, age_band varchar, children bigint, records bigint)
