-- Edge cases for dob_agreement_level. Returns failing cases; passes when empty.
with cases(dob_a, by_a, prec_a, dob_b, by_b, prec_b, expected) as (
    values
        (date '2015-03-14', 2015, 'DAY',  date '2015-03-14', 2015, 'DAY',  'EXACT'),
        (date '2015-03-04', 2015, 'DAY',  date '2015-04-03', 2015, 'DAY',  'DAY_MONTH_SWAPPED'),
        (date '2015-05-05', 2015, 'DAY',  date '2015-05-05', 2015, 'DAY',  'EXACT'),          -- day = month: swap is the same date
        (date '2015-05-06', 2015, 'DAY',  date '2015-06-05', 2015, 'DAY',  'DAY_MONTH_SWAPPED'),
        (date '2015-03-14', 2015, 'DAY',  date '2015-03-15', 2015, 'DAY',  'DIFFERENT'),
        (date '2015-03-14', 2015, 'DAY',  date '2014-03-14', 2014, 'DAY',  'YEAR_OFF_BY_ONE'), -- mistyped year
        (date '2015-03-14', 2015, 'DAY',  date '2014-09-02', 2014, 'DAY',  'DIFFERENT'),       -- siblings a year apart
        (date '2015-03-14', 2015, 'DAY',  date '2010-03-14', 2010, 'DAY',  'DIFFERENT'),
        (date '2016-02-29', 2016, 'DAY',  date '2016-02-29', 2016, 'DAY',  'EXACT'),           -- leap day
        (date '2016-02-29', 2016, 'DAY',  date '2016-02-28', 2016, 'DAY',  'DIFFERENT'),
        (date '2015-03-14', 2015, 'DAY',  null,              2015, 'YEAR', 'SAME_YEAR_ONLY'),
        (null,              2015, 'YEAR', null,              2015, 'YEAR', 'SAME_YEAR_ONLY'),
        (date '2015-03-14', 2015, 'DAY',  null,              2014, 'YEAR', 'YEAR_OFF_BY_ONE'),
        (date '2015-03-14', 2015, 'DAY',  null,              2012, 'YEAR', 'DIFFERENT'),
        (null,              null, null,   date '2015-03-14', 2015, 'DAY',  'MISSING'),          -- impossible DOB nulled upstream
        (date '2015-03-14', 2015, 'DAY',  null,              null, null,   'MISSING')
),
actual as (
    select *, {{ dob_agreement_level('dob_a', 'by_a', 'prec_a', 'dob_b', 'by_b', 'prec_b') }} as got from cases
)
select * from actual where got is distinct from expected
