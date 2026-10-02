{#-
  dob_agreement_level(dob_a, birth_year_a, precision_a, dob_b, birth_year_b, precision_b)
      EXACT              both DAY precision, same date
      DAY_MONTH_SWAPPED  both DAY precision, same year, day and month exchanged (day <= 12, day != month)
      SAME_YEAR_ONLY     at least one record has only a birth year (precision YEAR) and the years match
      YEAR_OFF_BY_ONE    birth years differ by 1 and either one side is YEAR precision, or both are DAY precision
                         with the same month and day (a mistyped year). Siblings born a year apart have
                         different month and day, so they stay DIFFERENT.
      DIFFERENT          anything else
      MISSING            either record has no birth year (impossible DOBs are nulled upstream)
  The levels describe agreement only; whether a DIFFERENT dob rules a pair out is decided by the matchers.
-#}
{% macro dob_agreement_level(dob_a, by_a, prec_a, dob_b, by_b, prec_b) -%}
case
    when {{ by_a }} is null or {{ by_b }} is null then 'MISSING'
    when {{ prec_a }} = 'DAY' and {{ prec_b }} = 'DAY' then
        case
            when {{ dob_a }} = {{ dob_b }} then 'EXACT'
            when {{ by_a }} = {{ by_b }}
                 and extract(month from {{ dob_a }}) = extract(day from {{ dob_b }})
                 and extract(day from {{ dob_a }}) = extract(month from {{ dob_b }})
                 and extract(day from {{ dob_a }}) <= 12
                 and extract(day from {{ dob_a }}) <> extract(month from {{ dob_a }}) then 'DAY_MONTH_SWAPPED'
            when abs({{ by_a }} - {{ by_b }}) = 1
                 and extract(month from {{ dob_a }}) = extract(month from {{ dob_b }})
                 and extract(day from {{ dob_a }}) = extract(day from {{ dob_b }}) then 'YEAR_OFF_BY_ONE'
            else 'DIFFERENT'
        end
    when {{ by_a }} = {{ by_b }} then 'SAME_YEAR_ONLY'
    when abs({{ by_a }} - {{ by_b }}) = 1 then 'YEAR_OFF_BY_ONE'
    else 'DIFFERENT'
end
{%- endmacro %}
