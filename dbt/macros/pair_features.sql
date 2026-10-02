{#-
  Shared by idr_pair_features (candidate pairs) and idr_u_probabilities (random pairs), so both compute
  feature levels in exactly the same way.

  pair_attributes()      the a_* / b_* columns for a pair, from aliases `a` and `b` over idr_input_records
  pair_level_ctes()      the CTEs `swapped` and `levels`, reading a CTE named `pairs`
-#}
{% macro pair_attributes() -%}
a.source_system as a_system, b.source_system as b_system,
a.first_name_key as a_first, a.last_name_key as a_last, b.first_name_key as b_first, b.last_name_key as b_last,
a.dob as a_dob, a.birth_year as a_by, a.dob_precision as a_prec,
b.dob as b_dob, b.birth_year as b_by, b.dob_precision as b_prec,
a.contact_email as a_email, b.contact_email as b_email,
a.contact_phone as a_phone, b.contact_phone as b_phone,
a.postal_code as a_postal, b.postal_code as b_postal,
a.sex as a_sex, b.sex as b_sex,
a.season_key as a_season, b.season_key as b_season,
a.organization_id as a_org, b.organization_id as b_org,
(a.country_code = 'JP' or b.country_code = 'JP') as swap_applicable
{%- endmacro %}

{% macro pair_level_ctes() -%}
swapped as (

    select *, swap_applicable and {{ name_order_swap_wins('a_first', 'a_last', 'b_first', 'b_last') }} as name_order_swapped
    from pairs

),

levels as (

    select
        record_a,
        record_b,
        blocks_hit,
        {{ source_pair('a_system', 'b_system') }}                           as source_pair,
        case when name_order_swapped then {{ name_similarity('a_first', 'b_last', 'last') }}
             else {{ name_similarity('a_first', 'b_first', 'first') }} end  as first_name_level,
        case when name_order_swapped then {{ name_similarity('a_last', 'b_first', 'last') }}
             else {{ name_similarity('a_last', 'b_last', 'last') }} end     as last_name_level,
        {{ dob_agreement_level('a_dob', 'a_by', 'a_prec', 'b_dob', 'b_by', 'b_prec') }} as dob_level,
        case when a_email is null or b_email is null then 'MISSING'
             when a_email = b_email then 'EXACT' else 'DIFFERENT' end       as email_level,
        case when a_phone is null or b_phone is null then 'MISSING'
             when a_phone = b_phone then 'EXACT' else 'DIFFERENT' end       as phone_level,
        case when a_postal is null or b_postal is null then 'MISSING'
             when a_postal = b_postal then 'EXACT'
             when left(a_postal, 3) = left(b_postal, 3) then 'PREFIX'       -- US zip3 or CA forward sortation area
             else 'DIFFERENT' end                                           as postal_level,
        case when a_sex = 'U' or b_sex = 'U' then 'UNKNOWN'
             when a_sex = b_sex then 'AGREE' else 'DISAGREE' end            as sex_level,
        case when a_season = b_season and a_org = b_org then 'SAME_ORG_SAME_SEASON'
             when a_season = b_season then 'SAME_SEASON_DIFF_ORG'
             else 'DIFF_SEASON' end                                         as context_level,
        name_order_swapped,
        a_prec = 'DAY' and b_prec = 'DAY'                                   as both_day_precision,
        abs(a_by - b_by)                                                    as birth_year_gap
    from swapped

)
{%- endmacro %}
