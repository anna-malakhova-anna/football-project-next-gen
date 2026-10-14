-- The retention-managed store (schema pii_store): a DERIVED copy of the parent and child side of Phase 5 that the age-out and revocation job is allowed to delete from.
-- The job never touches raw, eval, the dbt models or the published snapshots: raw stays the immutable source-system landing, this is the operational copy that retention governs.
-- retention_log and retained_aggregate hold COUNTS ONLY: no name, email, date of birth or id of a person.
create schema if not exists pii_store;
create table if not exists pii_store.child_record (
    feed varchar, source_record_id varchar, p5_person_id varchar, household_id varchar,
    first_name varchar, last_name varchar, birth_year integer, sex varchar, zip5 varchar, parent_email varchar,
    market_id varchar, age_band varchar, season_year integer, registered_at timestamp
);
create table if not exists pii_store.household_contact (household_id varchar, parent_email varchar);
create table if not exists pii_store.consent_event (
    consent_event_id varchar, household_id varchar, event_kind varchar, status varchar, purposes varchar, event_ts timestamp, registered_at timestamp
);
create table if not exists pii_store.household_activation (household_id varchar, eligible_for_club_activation boolean, activation_status varchar);
create table if not exists pii_store.revocation (household_id varchar, parent_email_hash varchar, revoked_at timestamp);
-- a do-not-contact list keeps only a one-way hash of the email, so a revoked parent is not contacted again after their data is gone
create table if not exists pii_store.suppression_list (parent_email_hash varchar, revoked_at timestamp, run_id varchar);
create table if not exists pii_store.retained_aggregate (run_id varchar, reason varchar, market_id varchar, age_band varchar, children bigint, records bigint);
create table if not exists pii_store.retention_log (
    run_id varchar, run_at timestamp, as_of date, rule varchar, table_name varchar, rows_deleted_or_changed bigint, children_affected bigint, households_affected bigint,
    age_out_age integer, grace_months integer, max_record_months integer, revocation_delay_days integer
)
