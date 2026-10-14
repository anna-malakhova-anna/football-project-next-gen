-- IMMEDIATE: a household that has revoked consent (as of the job date) leaves every activation-eligible set at once, before any deletion.
create or replace temp table _revoked_now as
select distinct household_id from pii_store.revocation where revoked_at <= cast('{as_of}' as date) + interval 1 day - interval 1 second;
create or replace temp table _revoked_changed as
select household_id from pii_store.household_activation where eligible_for_club_activation and household_id in (select household_id from _revoked_now);
update pii_store.household_activation set eligible_for_club_activation = false, activation_status = 'CONSENT_REVOKED'
where household_id in (select household_id from _revoked_now) and (eligible_for_club_activation or activation_status <> 'CONSENT_REVOKED')
