-- Edge cases for normalize_email. Returns failing cases; passes when empty.
with cases(input, fold, expected) as (
    values
        ('  Foo@Bar.COM ',        false, 'foo@bar.com'),
        ('foo@bar.com',           false, 'foo@bar.com'),
        ('',                      false, null),
        ('    ',                  false, null),
        (null,                    false, null),
        ('A.B+tag@Gmail.com',     false, 'a.b+tag@gmail.com'),   -- folding is off by default
        ('A.B+tag@Gmail.com',     true,  'ab@gmail.com'),
        ('a.b@googlemail.com',    true,  'ab@googlemail.com'),
        ('a.b+tag@example.com',   true,  'a.b+tag@example.com'),  -- only Gmail is folded
        ('no-at-sign',            true,  'no-at-sign'),
        (' ',                     true,  null)
),
actual as (
    select input, fold, expected,
        case when fold then {{ normalize_email('input', fold_gmail=true) }}
             else {{ normalize_email('input', fold_gmail=false) }} end as got
    from cases
)
select * from actual where got is distinct from expected
