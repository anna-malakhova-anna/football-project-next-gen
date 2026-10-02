{{ config(tags=['phase3']) }}
-- age_band and term_order edge cases. Returns failing cases; passes when empty.
with bands(age, expected) as (
    values (cast(null as integer), 'UNKNOWN'), (-1, '0-7'), (4, '0-7'), (7, '0-7'), (8, '8-9'), (9, '8-9'), (10, '10-11'),
           (11, '10-11'), (12, '12-13'), (13, '12-13'), (14, '14-17'), (17, '14-17'), (18, '18-29'), (29, '18-29'),
           (30, '30-44'), (44, '30-44'), (45, '45+'), (80, '45+')
),
terms(term, expected) as (values ('SPRING', 1), ('ANNUAL', 2), ('FALL', 3))
select 'age_band' as macro, cast(age as varchar) as input, expected, {{ age_band('age') }} as got from bands
where {{ age_band('age') }} is distinct from expected
union all
select 'term_order', term, cast(expected as varchar), cast({{ term_order('term') }} as varchar) from terms
where {{ term_order('term') }} is distinct from expected
