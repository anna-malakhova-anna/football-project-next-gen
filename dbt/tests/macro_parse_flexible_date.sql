-- Edge cases for parse_flexible_date / parse_flexible_date_status. Returns failing cases.
with cases(input, fmt, expected_date, expected_status) as (
    values
        ('03/14/2015',   'MDY', date '2015-03-14', 'PARSED_MDY'),
        ('3/4/2015',     'MDY', date '2015-03-04', 'PARSED_MDY'),
        ('14/03/2015',   'DMY', date '2015-03-14', 'PARSED_DMY'),
        ('14/03/2015',   'MDY', null,              'UNPARSEABLE'),  -- month 14: not coerced
        ('03/14/2015',   'DMY', null,              'UNPARSEABLE'),
        ('02/30/2015',   'MDY', null,              'UNPARSEABLE'),  -- looks like a date, is not one
        ('02/29/2016',   'MDY', date '2016-02-29', 'PARSED_MDY'),   -- leap day
        ('02/29/2015',   'MDY', null,              'UNPARSEABLE'),
        ('03/04/2015',   'ANY', null,              'AMBIGUOUS'),    -- never guess
        ('13/04/2015',   'ANY', date '2015-04-13', 'PARSED_DMY'),
        ('04/13/2015',   'ANY', date '2015-04-13', 'PARSED_MDY'),
        ('05/05/2015',   'ANY', date '2015-05-05', 'PARSED_MDY'),   -- both readings agree
        ('2015-03-14',   'MDY', date '2015-03-14', 'PARSED_ISO'),
        ('2015-03-14',   'DMY', date '2015-03-14', 'PARSED_ISO'),
        (' 2015-03-14 ', 'ANY', date '2015-03-14', 'PARSED_ISO'),
        ('2015-02-30',   'ANY', null,              'UNPARSEABLE'),
        ('42298',        'DMY', date '2015-10-21', 'EXCEL_SERIAL'),
        ('10000',        'DMY', date '1927-05-18', 'EXCEL_SERIAL'),
        ('2015',         'DMY', null,              'UNPARSEABLE'),  -- a year is not a serial
        ('March 14',     'ANY', null,              'UNPARSEABLE'),
        ('',             'ANY', null,              'BLANK'),
        ('   ',          'ANY', null,              'BLANK'),
        (null,           'ANY', null,              'BLANK')
),
actual as (
    select input, fmt, expected_date, expected_status,
        case fmt
            when 'MDY' then {{ parse_flexible_date('input', 'MDY') }}
            when 'DMY' then {{ parse_flexible_date('input', 'DMY') }}
            else {{ parse_flexible_date('input', 'ANY') }} end as got_date,
        case fmt
            when 'MDY' then {{ parse_flexible_date_status('input', 'MDY') }}
            when 'DMY' then {{ parse_flexible_date_status('input', 'DMY') }}
            else {{ parse_flexible_date_status('input', 'ANY') }} end as got_status
    from cases
)
select * from actual
where got_date is distinct from expected_date or got_status is distinct from expected_status
