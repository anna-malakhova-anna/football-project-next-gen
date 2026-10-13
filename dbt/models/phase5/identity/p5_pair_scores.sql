-- Phase 5 matching: the Phase 2 pair features and the Phase 2 ordered rules (macro idr_rules_rule_id: R1 to R6), plus ONE Phase 5 extension.
--   R7 first name EXACT (a nickname is not enough: James and Jamie in one family are siblings) + last name exact + parent email exact + DOB MISSING on a side,
--      and where one side has an age group the other side's age must fall inside it  -> AUTO_MATCH
--      (vendor_reg_b carries an age group, not a DOB, so R1 to R5 can never fire for it; same child name and same parent email in the same state is the
--       strongest evidence such a feed offers. Twins and siblings have different first names, so the sibling guard R4 still holds. Evaluated against the answer key
--       in eval_p5_resolution, never tuned to it.)
-- Records without a DOB and without an email (school rosters) cannot be matched safely and stay separate: precision first.
with pairs as (

    select c.record_a, c.record_b, c.blocks_hit, {{ pair_attributes() }},
           a.age_group_cap as a_cap, b.age_group_cap as b_cap, a.age_at_cutoff as a_age, b.age_at_cutoff as b_age
    from {{ ref('p5_candidate_pairs') }} c
    join {{ ref('p5_idr_input_records') }} a on a.match_record_id = c.record_a
    join {{ ref('p5_idr_input_records') }} b on b.match_record_id = c.record_b

),

{{ pair_level_ctes() }},

ruled as (

    select
        l.*, p.a_cap, p.b_cap, p.a_age, p.b_age,
        case when first_name_level = 'EXACT' and last_name_level = 'EXACT' and dob_level = 'MISSING' and email_level = 'EXACT'
                  and coalesce(a_age between b_cap - 3 and b_cap, true) and coalesce(b_age between a_cap - 3 and a_cap, true)
             then 'R7' else {{ idr_rules_rule_id() }} end                   as rule_id
    from levels l join pairs p on p.record_a = l.record_a and p.record_b = l.record_b

)

select
    record_a,
    record_b,
    rule_id,
    case when rule_id in ('R1', 'R2', 'R7') then 'AUTO_MATCH' when rule_id in ('R3', 'R5') then 'PROBABLE' else 'NON_MATCH' end as tier,
    case rule_id
        when 'R1' then 'first name exact or nickname, last name exact, DOB exact'
        when 'R2' then 'first name exact or nickname, last name exact, same birth year, email exact'
        when 'R3' then 'first name close, last name exact, DOB exact or day/month swapped'
        when 'R4' then 'same email and DOB but different first name: siblings or twins, never a match'
        when 'R5' then 'names exact, birth year off by one, email exact'
        when 'R7' then 'Phase 5 extension: names exact, parent email exact, DOB missing on one side, age consistent with the age group'
        else 'no rule matched'
    end                                                                     as reason
from ruled
