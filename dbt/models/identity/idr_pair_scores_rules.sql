-- Matcher A: a deliberately simple, ordered rules baseline. The first matching rule decides the tier.
-- Its job is to be a credible baseline, not to win. Every row says which rule fired and why.
--   R1 first EXACT/NICKNAME + last EXACT + dob EXACT                                  -> AUTO_MATCH
--   R2 first EXACT/NICKNAME + last EXACT + dob SAME_YEAR_ONLY + (email or phone EXACT) -> AUTO_MATCH
--   R3 first FUZZY_HIGH + last EXACT + dob EXACT or DAY_MONTH_SWAPPED                  -> PROBABLE
--   R4 email EXACT + dob EXACT + first DIFFERENT                                       -> NON_MATCH (sibling/twin guard)
--   R5 last EXACT + dob YEAR_OFF_BY_ONE + first EXACT + (email or phone EXACT)         -> PROBABLE
--   R6 everything else                                                                 -> NON_MATCH
with f as (select * from {{ ref('idr_pair_features') }}),

ruled as (

    select
        *,
        {{ idr_rules_rule_id() }} as rule_id
    from f

)

select
    record_a,
    record_b,
    'rules'                                                                 as matcher,
    rule_id,
    case rule_id when 'R1' then 'AUTO_MATCH' when 'R2' then 'AUTO_MATCH'
                 when 'R3' then 'PROBABLE' when 'R5' then 'PROBABLE' else 'NON_MATCH' end as tier,
    case rule_id
        when 'R1' then 'first name exact or nickname, last name exact, DOB exact'
        when 'R2' then 'first name exact or nickname, last name exact, same birth year, email or phone exact'
        when 'R3' then 'first name close, last name exact, DOB exact or day/month swapped'
        when 'R4' then 'same email and DOB but different first name: siblings or twins, never a match'
        when 'R5' then 'names exact, birth year off by one, email or phone exact'
        else 'no rule matched'
    end                                                                     as reason
from ruled
