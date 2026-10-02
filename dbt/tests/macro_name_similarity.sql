-- Edge cases for name_similarity and name_order_swap_wins. Returns failing cases; passes when empty.
with first_cases(a, b, expected) as (
    values
        ('elodie',      'elodie',      'EXACT'),
        ('elodie',      '',            'MISSING'),
        (null,          'elodie',      'MISSING'),
        ('robert',      'bob',         'NICKNAME'),
        ('bob',         'robert',      'NICKNAME'),     -- both directions
        ('christopher', 'chris',       'NICKNAME'),
        ('francisco',   'paco',        'NICKNAME'),     -- Spanish
        ('frederic',    'fred',        'NICKNAME'),     -- French, accent-stripped key
        ('bob',         'rob',         'DIFFERENT'),    -- two nicknames of Robert are not linked
        ('jon',         'john',        'FUZZY_HIGH'),
        ('elisabeth',   'elizabeth',   'FUZZY_HIGH'),
        ('jean-luc',    'jean luc',    'FUZZY_HIGH'),   -- hyphen vs space
        ('kim',         'kimberly',    'NICKNAME'),
        ('brian',       'bryan',       'FUZZY_LOW'),    -- JW 0.893
        ('caleb',       'kaleb',       'FUZZY_LOW'),    -- JW 0.867
        ('anna',        'maria',       'DIFFERENT')
),
last_cases(a, b, expected) as (
    values
        ('smith',       'smith',       'EXACT'),
        ('smith',       null,          'MISSING'),
        ('smith',       'smyth',       'FUZZY_LOW'),    -- JW 0.893
        ('tremblay',    'trembly',     'FUZZY_HIGH'),
        ('smith',       'smith-jones', 'FUZZY_HIGH'),   -- hyphenated after marriage
        ('smith-jones', 'jones',       'FUZZY_HIGH'),
        ('okada',       'okada-inoue', 'FUZZY_HIGH'),
        ('miller',      'muller',      'FUZZY_LOW'),    -- different surnames that look alike
        ('okada',       'rudolph',     'DIFFERENT'),    -- a plain family-name change: not recoverable
        ('lopez',       'hernandez',   'DIFFERENT')
),
swap_cases(a_first, a_last, b_first, b_last, expected) as (
    values
        ('hanako', 'sato',   'sato',   'hanako', true),    -- Japanese order on one record
        ('hanako', 'sato',   'hanako', 'sato',   false),   -- already agree
        ('sato',   'hanako', 'sato',   'hanako', false),
        ('hanako', 'sato',   'taro',   'suzuki', false),   -- nothing agrees either way
        ('hanako', 'hanako', 'hanako', 'hanako', false)    -- tie: keep the normal order
)
select 'first' as kind, a, b, expected, {{ name_similarity('a', 'b', 'first') }} as got from first_cases
    where {{ name_similarity('a', 'b', 'first') }} is distinct from expected
union all
select 'last', a, b, expected, {{ name_similarity('a', 'b', 'last') }} from last_cases
    where {{ name_similarity('a', 'b', 'last') }} is distinct from expected
union all
select 'swap', a_first || '/' || a_last, b_first || '/' || b_last, cast(expected as varchar),
    cast({{ name_order_swap_wins('a_first', 'a_last', 'b_first', 'b_last') }} as varchar)
from swap_cases
where {{ name_order_swap_wins('a_first', 'a_last', 'b_first', 'b_last') }} is distinct from expected
