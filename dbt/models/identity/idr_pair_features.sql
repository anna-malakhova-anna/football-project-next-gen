-- One row per candidate pair: agreement LEVELS (not raw scores), so the same features feed both matchers.
-- Name logic is in the name_similarity macro, DOB logic in dob_agreement_level; the level definitions live in
-- macros/pair_features.sql (shared with idr_u_probabilities). Season means year + term.
-- For Japanese records (family name first on the federation sheet) the swapped first/last comparison is also
-- tried and used when it agrees better; name_order_swapped records that.
with pairs as (

    select c.record_a, c.record_b, c.blocks_hit, {{ pair_attributes() }}
    from {{ ref('idr_candidate_pairs') }} c
    join {{ ref('idr_input_records') }} a on a.match_record_id = c.record_a
    join {{ ref('idr_input_records') }} b on b.match_record_id = c.record_b

),

{{ pair_level_ctes() }}

select
    *,
    -- two kids from one household registered together: the main thing a naive matcher gets wrong
    context_level = 'SAME_ORG_SAME_SEASON' and first_name_level = 'DIFFERENT'
        and (email_level = 'EXACT' or phone_level = 'EXACT')                as sibling_twin_signal
from levels
