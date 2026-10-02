{{ config(tags=['phase3']) }}
-- pseudonymize edge cases (explicit salts, so the test does not depend on the environment). Returns failing cases.
with t(id, salt_a, salt_b) as (
    values ('P-AAAAAAAAAAAA', 's1', 's2'), ('P-BBBBBBBBBBBB', 's1', 's2'), ('p-aaaaaaaaaaaa', 's1', 's2'), ('', 's1', 's2'), (cast(null as varchar), 's1', 's2')
),
x as (
    select id, salt_a,
        {{ pseudonymize('id', salt='s1') }} as a1,
        {{ pseudonymize('id', salt='s1') }} as a2,
        {{ pseudonymize('id', salt='s2') }} as b,
        {{ pseudonymize('id', salt="it's") }} as quoted
    from t
)
select 'null_must_stay_null' as problem, coalesce(id, '<null>') as detail from x where id is null and a1 is not null
union all
select 'not_deterministic', id from x where id is not null and a1 <> a2
union all
select 'salt_has_no_effect', id from x where id is not null and a1 = b
union all
select 'not_64_hex', id from x where id is not null and not regexp_matches(a1, '^[0-9a-f]{64}$')
union all
select 'leaks_the_id', id from x where id is not null and id <> '' and contains(a1, lower(id))
union all
select 'case_sensitive_ids_collide', 'P-AAAAAAAAAAAA' from x x1 join x x2 on x1.id = 'P-AAAAAAAAAAAA' and x2.id = 'p-aaaaaaaaaaaa' and x1.a1 = x2.a1
union all
select 'two_ids_collide', a1 from x where id is not null group by a1 having count(*) > 1
union all
select 'quote_in_salt_breaks_sql', id from x where id is not null and quoted is null
