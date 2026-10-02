-- Edge cases for the cleaning helpers. Returns failing cases; passes when empty.
with phone(input, cc, expected) as (
    values
        ('(512) 555-0142',   '1', '+15125550142'),
        ('512.555.0142',     '1', '+15125550142'),
        ('5125550142',       '1', '+15125550142'),
        ('+1 514 555 0199',  '1', '+15145550199'),
        ('1-514-555-0199',   '1', '+15145550199'),
        ('555-0142',         '1', null),            -- 7 digits: not guessed
        ('25125550142',      '1', null),            -- 11 digits not starting with the country code
        ('',                 '1', null),
        (null,               '1', null)
),
consent(input, expected) as (
    values
        ('Y', true), ('yes', true), ('TRUE', true), ('true', true), (' y ', true),
        ('N', false), ('no', false), ('FALSE', false),
        ('', null), ('   ', null), (null, null), ('maybe', null)   -- blank is NEVER false
),
zip(input, expected) as (
    values
        ('07302', '07302'), ('7302', '07302'), ('75969', '75969'), ('07302-1234', '07302'),
        (' 90210 ', '90210'), ('123', null), ('ABCDE', null), ('', null), (null, null)
),
postal(input, expected) as (
    values
        ('H1X 2B3', 'H1X 2B3'), ('h1x2b3', 'H1X 2B3'), ('H1X2B3', 'H1X 2B3'), ('h1x 2b3', 'H1X 2B3'),
        (' K1A 0B1 ', 'K1A 0B1'), ('12345', null), ('H1X 2B', null), ('', null), (null, null)
)
select 'phone' as macro, input, expected, {{ normalize_phone('input', '1') }} as got from phone
    where {{ normalize_phone('input', '1') }} is distinct from expected
union all
select 'consent', input, cast(expected as varchar), cast({{ to_consent_boolean('input') }} as varchar) from consent
    where {{ to_consent_boolean('input') }} is distinct from expected
union all
select 'us_zip', input, expected, {{ normalize_us_zip('input') }} from zip
    where {{ normalize_us_zip('input') }} is distinct from expected
union all
select 'ca_postal', input, expected, {{ normalize_ca_postal('input') }} from postal
    where {{ normalize_ca_postal('input') }} is distinct from expected
