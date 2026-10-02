{#-
  name_similarity(a, b, kind)  -> agreement level of two name KEYS (lowercase, accent-stripped; see name_key)
      first: EXACT | NICKNAME | FUZZY_HIGH | FUZZY_LOW | DIFFERENT | MISSING
      last : EXACT | FUZZY_HIGH | FUZZY_LOW | DIFFERENT | MISSING
  NICKNAME looks the pair up in the nickname_map seed in both directions (robert/bob and bob/robert).
  Last names also count as FUZZY_HIGH when every token of one appears in the other (smith / smith-jones):
  a hyphenated or compound surname after marriage is not a typo, but it is closer than "different".
  FUZZY_HIGH / FUZZY_LOW use Jaro-Winkler against vars name_fuzzy_high (0.92) and name_fuzzy_low (0.85).
  Missing means NULL or empty. Nothing is compared against missing, and nothing is ever guessed.

  name_level_rank(level)           -> 0 (MISSING) .. 5 (EXACT), to compare two levels
  name_order_swap_wins(af, al, bf, bl)
      TRUE when comparing a.first with b.last and a.last with b.first agrees better than the normal order.
      Only evaluated for records the caller marks as family-name-first (Japan); see idr_pair_features.

  DuckDB-specific: jaro_winkler_similarity, string_split, list_has_all, regexp_replace(..., 'g').
  Snowflake: JAROWINKLER_SIMILARITY (0-100, so divide by 100), SPLIT, ARRAY_CONTAINS per token. See ADR-003.
-#}
{% macro name_similarity(a, b, kind='first') -%}
{%- set hi = var('name_fuzzy_high') -%}
{%- set lo = var('name_fuzzy_low') -%}
case
    when nullif({{ a }}, '') is null or nullif({{ b }}, '') is null then 'MISSING'
    when {{ a }} = {{ b }} then 'EXACT'
    {%- if kind == 'first' %}
    when exists (
        select 1 from {{ ref('nickname_map') }} _nm
        where (_nm.given_key = {{ a }} and _nm.nickname_key = {{ b }})
           or (_nm.given_key = {{ b }} and _nm.nickname_key = {{ a }})
    ) then 'NICKNAME'
    {%- elif kind == 'last' %}
    when list_has_all(string_split(regexp_replace({{ a }}, '[-\s]+', ' ', 'g'), ' '), string_split(regexp_replace({{ b }}, '[-\s]+', ' ', 'g'), ' '))
      or list_has_all(string_split(regexp_replace({{ b }}, '[-\s]+', ' ', 'g'), ' '), string_split(regexp_replace({{ a }}, '[-\s]+', ' ', 'g'), ' '))
        then 'FUZZY_HIGH'
    {%- else %}{{ exceptions.raise_compiler_error("name_similarity: kind must be first or last") }}
    {%- endif %}
    when jaro_winkler_similarity({{ a }}, {{ b }}) >= {{ hi }} then 'FUZZY_HIGH'
    when jaro_winkler_similarity({{ a }}, {{ b }}) >= {{ lo }} then 'FUZZY_LOW'
    else 'DIFFERENT'
end
{%- endmacro %}

{% macro name_level_rank(level) -%}
case {{ level }}
    when 'EXACT' then 5 when 'NICKNAME' then 4 when 'FUZZY_HIGH' then 3
    when 'FUZZY_LOW' then 2 when 'DIFFERENT' then 1 else 0
end
{%- endmacro %}

{% macro name_order_swap_wins(a_first, a_last, b_first, b_last) -%}
(
    {{ name_level_rank(name_similarity(a_first, b_last, 'last')) }} + {{ name_level_rank(name_similarity(a_last, b_first, 'last')) }}
    > {{ name_level_rank(name_similarity(a_first, b_first, 'first')) }} + {{ name_level_rank(name_similarity(a_last, b_last, 'last')) }}
)
{%- endmacro %}
