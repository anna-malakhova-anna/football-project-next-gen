-- Edge cases for normalize_name and name_key. Returns failing cases; passes when empty.
with cases(input, expected_name, expected_key) as (
    values
        ('TREMBLAY',              'Tremblay',        'tremblay'),
        ('  mary   ann ',         'Mary Ann',        'mary ann'),
        ('jean-luc',              'Jean-Luc',        'jean-luc'),
        ('O''BRIEN',              'O''Brien',        'o''brien'),
        ('McDaniel',              'McDaniel',        'mcdaniel'),     -- mixed case is kept
        ('Élodie',                'Élodie',          'elodie'),
        ('ÉLODIE',                'Élodie',          'elodie'),
        ('Elodie',                'Elodie',          'elodie'),       -- same key as the accented form
        ('maría josé hernández lópez', 'María José Hernández López', 'maria jose hernandez lopez'),
        ('Zoë',                   'Zoë',             'zoe'),
        ('',                      null,              null),
        ('   ',                   null,              null),
        (null,                    null,              null),
        ('X',                     'X',               'x')
),
actual as (
    select input, expected_name, expected_key,
        {{ normalize_name('input') }} as got_name,
        {{ name_key('input') }} as got_key
    from cases
)
select * from actual
where got_name is distinct from expected_name or got_key is distinct from expected_key
