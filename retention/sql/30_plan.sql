-- Decide what is due. A child is judged on the OLDEST plausible birth year among their records (a typo that makes a child look younger must not extend retention).
--   REVOKED  the child's household revoked consent and revocation_delay_days have passed          -> all of the child's records
--   AGE_OUT  Dec 31 of (birth year + age_out_age) plus grace_months has passed                    -> all of the child's records
--   MAX_AGE  a registration is older than max_record_months, whatever the child's age             -> that record
-- Precedence for counting: REVOKED, then AGE_OUT, then MAX_AGE; each record is counted once.
create or replace temp table _child_ref as
select p5_person_id, any_value(household_id) as household_id, min(birth_year) filter (where birth_year >= 1900) as ref_birth_year
from pii_store.child_record group by 1;
create or replace temp table _due_children as
select
    c.p5_person_id,
    case when r.household_id is not null then 'REVOKED'
         when c.ref_birth_year is not null and cast(make_date(c.ref_birth_year + {age_out_age}, 12, 31) + to_months({grace_months}) as date) <= cast('{as_of}' as date) then 'AGE_OUT'
    end as reason
from _child_ref c
left join (select distinct household_id from pii_store.revocation where cast(revoked_at as date) + {revocation_delay_days} <= cast('{as_of}' as date)) r on r.household_id = c.household_id
where r.household_id is not null
   or (c.ref_birth_year is not null and cast(make_date(c.ref_birth_year + {age_out_age}, 12, 31) + to_months({grace_months}) as date) <= cast('{as_of}' as date));
create or replace temp table _due_records as
select r.feed, r.source_record_id, r.p5_person_id, coalesce(d.reason, 'MAX_AGE') as reason, r.market_id, r.age_band
from pii_store.child_record r left join _due_children d using (p5_person_id)
where d.p5_person_id is not null or cast(r.registered_at as date) + to_months({max_record_months}) <= cast('{as_of}' as date)
