-- Matcher B: Fellegi-Sunter probabilistic matching, in two variants that share the same weights:
--   fs_naive  the textbook model: features are independent, weights are summed.
--   fs        the same weights, with two structural corrections for household-shared evidence:
--               1. email, phone and postal code are three views of one household, so only the strongest of the
--                  three counts (summing them triple-counts "same household");
--               2. HOUSEHOLD_GUARD: same email or phone but a clearly different first name means two people
--                  sharing a household (siblings, twins), never a match.
--             The grouping counts the strongest POSITIVE contact weight once but every NEGATIVE one: the three
--             agree because they share a household (correlated), while a changed email and a changed phone are
--             separate events (independent).
--               3. DOB_DISAGREE_CAP: a DOB that disagrees (a birth year one apart, or a different date that the
--                  DOB-conflict guard does not rule out) cannot be AUTO_MATCH. Siblings look exactly like this, and
--                  the rules baseline (R5) also sends a year-off-by-one pair to review.
--             These were added after the naive variant's evaluation showed sibling, twin and common-name false
--             merges; the history, and what it says about conditional independence, is in ADR-003.
--   weight(feature, level) = log2(m / u)      m: assumed (seed, documented), u: estimated from random pairs
--   match_weight           = sum of counted weights; MISSING contributes 0
--   match_probability      = 2^w * L / (1 + 2^w * L), L = prior odds of a match among candidate pairs (seed)
-- Hard overrides then apply to both variants:
--   twin/sibling guard   same org + same season + different first name        -> NON_MATCH
--   DOB conflict         DOB DIFFERENT, both day precision, years > 1 apart   -> NON_MATCH
--   sex disagreement     sex DISAGREE (both F/M)                              -> capped at PROBABLE
-- (fs only: the household guard and the DOB disagreement cap described above.)
-- Tiers come from the thresholds seed. weight_breakdown shows every feature's level, weight and whether it counted.
{% set features = [
    ('first_name', 'first_name_level'), ('last_name', 'last_name_level'), ('dob', 'dob_level'),
    ('email', 'email_level'), ('phone', 'phone_level'), ('postal', 'postal_level'),
    ('sex', 'sex_level'), ('context', 'context_level')
] %}
{% set variants = [('fs_naive', false), ('fs', true)] %}

with weights as (

    select
        m.feature,
        m.level,
        case when m.level = 'MISSING' then 0.0 else log2(m.m_probability / u.u_probability) end as weight
    from {{ ref('match_m_probabilities') }} m
    join {{ ref('idr_u_probabilities') }} u using (feature, level)

),

weighted as (

    select
        f.*,
        {% for feature, col in features %}coalesce(w_{{ feature }}.weight, 0.0) as weight_{{ feature }},
        {% endfor %}
        -- the strongest of the three household-shared weights (the one positive weight that counts when grouped)
        case when coalesce(w_email.weight, 0) >= coalesce(w_phone.weight, 0)
                  and coalesce(w_email.weight, 0) >= coalesce(w_postal.weight, 0) then 'email'
             when coalesce(w_phone.weight, 0) >= coalesce(w_postal.weight, 0) then 'phone'
             else 'postal' end as contact_counted
    from {{ ref('idr_pair_features') }} f
    {% for feature, col in features %}
    left join weights w_{{ feature }} on w_{{ feature }}.feature = '{{ feature }}' and w_{{ feature }}.level = f.{{ col }}
    {% endfor %}

),

{% for matcher, grouped in variants %}
{{ matcher }}_scored as (

    select
        w.*,
        '{{ matcher }}' as matcher,
        {% for feature, col in features %}
        {%- if grouped and feature in ['email', 'phone', 'postal'] -%}
        case when weight_{{ feature }} < 0 or contact_counted = '{{ feature }}' then weight_{{ feature }} else 0.0 end as counted_{{ feature }},
        {%- else -%}
        weight_{{ feature }} as counted_{{ feature }},
        {%- endif %}
        {% endfor %}
        t.prior_odds, t.t_auto, t.t_review,
        {{ 'true' if grouped else 'false' }} as grouped
    from weighted w
    cross join (select * from {{ ref('match_thresholds') }} where matcher_version = '{{ matcher }}') t

),
{% endfor %}

scored as (

    {% for matcher, grouped in variants %}
    select *, {% for feature, col in features %}counted_{{ feature }}{{ ' + ' if not loop.last }}{% endfor %} as match_weight from {{ matcher }}_scored
    {{ 'union all' if not loop.last }}
    {% endfor %}

),

tiered as (

    select
        *,
        1.0 / (1.0 + pow(2.0, -match_weight) / prior_odds)                  as match_probability
    from scored

),

with_tier as (

    select
        *,
        case when match_probability >= t_auto then 'AUTO_MATCH'
             when match_probability >= t_review then 'PROBABLE'
             else 'NON_MATCH' end                                            as base_tier,
        (context_level = 'SAME_ORG_SAME_SEASON' and first_name_level = 'DIFFERENT')       as guard_twin_sibling,
        (dob_level = 'DIFFERENT' and both_day_precision and birth_year_gap > 1)           as guard_dob_conflict,
        (sex_level = 'DISAGREE')                                             as guard_sex_cap,
        (grouped and first_name_level = 'DIFFERENT' and (email_level = 'EXACT' or phone_level = 'EXACT'))
                                                                            as guard_household,
        (grouped and dob_level in ('YEAR_OFF_BY_ONE', 'DIFFERENT'))                 as guard_dob_cap
    from tiered

)

select
    record_a,
    record_b,
    matcher,
    round(match_weight, 3)                                                  as match_weight,
    match_probability,
    base_tier,
    case
        when guard_twin_sibling or guard_dob_conflict or guard_household then 'NON_MATCH'
        when (guard_sex_cap or guard_dob_cap) and base_tier = 'AUTO_MATCH' then 'PROBABLE'
        else base_tier
    end                                                                     as tier,
    case
        when guard_twin_sibling then 'TWIN_SIBLING_GUARD'
        when guard_household then 'HOUSEHOLD_GUARD'
        when guard_dob_conflict then 'DOB_CONFLICT'
        when guard_sex_cap and base_tier = 'AUTO_MATCH' then 'SEX_DISAGREE_CAP'
        when guard_dob_cap and base_tier = 'AUTO_MATCH' then 'DOB_DISAGREE_CAP'
    end                                                                     as override_applied,
    guard_twin_sibling or guard_dob_conflict or guard_household             as forced_non_match,
    guard_sex_cap or guard_dob_cap                                         as capped_at_probable,
    json_object(
        {% for feature, col in features %}'{{ feature }}', json_object('level', {{ col }}, 'weight', round(weight_{{ feature }}, 2), 'counted', round(counted_{{ feature }}, 2)){{ ',' if not loop.last }}
        {% endfor %}
    )                                                                       as weight_breakdown,
    'weight ' || round(match_weight, 1) || ' = ' ||
        {% for feature, col in features %}'{{ feature }} ' || {{ col }} || ' (' || round(counted_{{ feature }}, 1) || ')'{{ " || ', ' || " if not loop.last }}
        {% endfor %}
                                                                            as reason
from with_tier
