-- Edge cases for age_at_cutoff (default Dec 31 cutoff, ADR-002). Returns failing cases.
with cases(dob, season_year, cutoff, expected) as (
    values
        (date '2015-03-14', 2024, '12-31', 9),
        (date '2015-12-31', 2024, '12-31', 9),    -- born on the cutoff day: already 9
        (date '2016-02-29', 2024, '12-31', 8),    -- leap-day birthday
        (date '2024-12-31', 2024, '12-31', 0),
        (date '2026-01-01', 2024, '12-31', -2),   -- future DOB: negative, left for the impossible-DOB flag
        (date '1940-06-01', 2024, '12-31', 84),
        (date '2015-08-31', 2024, '08-31', 9),    -- alternative cutoff: birthday on cutoff counts
        (date '2015-09-01', 2024, '08-31', 8),    -- birthday the day after the cutoff does not
        (cast(null as date), 2024, '12-31', null)
),
actual as (
    select dob, season_year, cutoff, expected,
        case when cutoff = '12-31' then {{ age_at_cutoff('dob', 'season_year') }}
             else {{ age_at_cutoff('dob', 'season_year', cutoff_month_day='08-31') }} end as got,
        {{ age_at_cutoff_from_birth_year('2013', '2024') }} as got_by
    from cases
)
select * from actual
where got is distinct from expected or got_by != 11
