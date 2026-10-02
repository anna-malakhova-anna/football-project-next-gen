{#-
  suppress_small_cells(relation, dims, count_cols, secondary_col=none, rates={}, passthrough=[], k=none)

  Small-cell suppression for aggregate shares (ADR-006), applied to a table that is a HIERARCHY of cells:
  `dims` is the ordered list of dimension columns (for example year, country, age band); a NULL dimension means "rolled
  up", so a row's depth is its number of non-NULL dims and its parent is the row with the same leading dims one level up.

    PRIMARY    a count above zero and below k (privacy_params k_min, default 10) is set to NULL.
               Zero is NOT suppressed: a published zero reveals no individual (ADR-006 explains this choice).
    SECONDARY  within a group of sibling cells that has a PUBLISHED parent (subtotal), if exactly one cell is
               primary-suppressed, the next smallest NON-ZERO cell of the group is suppressed too (hiding a zero protects
               nothing), so the hidden value cannot be recovered by subtraction. Decided on `secondary_col`, the count
               that partitions the parent.
    rates      derived rates are NULL whenever any component count is suppressed or small, or the row is suppressed:
               rates={'girls_share_of_youth': ['youth_girls_participants', 'youth_participants']}.

  `relation` must hold dims, count_cols, passthrough columns and every rate component. Returns dims, count_cols (with
  suppressed values NULL), rates, passthrough and `suppressed` (NONE / PRIMARY / SECONDARY, the strongest on the row).
  Every column is listed explicitly (no select *), as the share policy requires.
  This is simplified disclosure control; production would use a method such as those in sdcMicro or tau-Argus.
-#}
{% macro suppress_small_cells(relation, dims, count_cols, secondary_col=none, rates={}, passthrough=[], k=none) -%}
{%- set kk = k if k is not none else privacy_param('k_min') -%}
{%- set sec = secondary_col if secondary_col is not none else count_cols[0] -%}
{%- set n = dims | length -%}
{%- set ns = namespace(cols=[]) -%}
{%- for c in dims + count_cols + passthrough + (rates.keys() | list) -%}{%- if c not in ns.cols -%}{%- set ns.cols = ns.cols + [c] -%}{%- endif -%}{%- endfor -%}
{%- for rate, comps in rates.items() -%}{%- for c in comps -%}{%- if c not in ns.cols -%}{%- set ns.cols = ns.cols + [c] -%}{%- endif -%}{%- endfor -%}{%- endfor -%}
{%- if sec not in ns.cols -%}{%- set ns.cols = ns.cols + [sec] -%}{%- endif -%}
(
    with src as (

        select
            {% for c in ns.cols %}{{ c }},
            {% endfor %}
            {% for i in range(n) %}case when {{ dims[i] }} is not null then 1 else 0 end{{ ' + ' if not loop.last }}{% endfor %} as _depth,
            concat_ws('|', {% for d in dims %}{{ d }}{{ ', ' if not loop.last }}{% endfor %}) as _node
        from {{ relation }}

    ),

    keyed as (

        select
            {% for c in ns.cols %}{{ c }},
            {% endfor %}
            _depth,
            _node,
            -- parent node: the same leading dims, one level up
            {% if n > 1 -%}
            case _depth
                {% for i in range(1, n) %}when {{ i + 1 }} then concat_ws('|', {% for j in range(i) %}{{ dims[j] }}{{ ', ' if not loop.last }}{% endfor %})
                {% endfor %}
                else null
            end
            {%- else -%}
            cast(null as varchar)
            {%- endif %} as _parent,
            ({{ sec }} > 0 and {{ sec }} < {{ kk }}) as _primary_sec
            {%- for c in count_cols %},
            ({{ c }} > 0 and {{ c }} < {{ kk }}) as _prim_{{ loop.index }}
            {%- endfor %}
            {%- for rate, comps in rates.items() %},
            ({% for c in comps %}({{ c }} > 0 and {{ c }} < {{ kk }}){{ ' or ' if not loop.last }}{% endfor %}) as _small_{{ rate }}
            {%- endfor %}
        from src

    ),

    grp as (

        select
            {% for c in ns.cols %}k.{{ c }},
            {% endfor %}
            k._depth, k._node, k._parent, k._primary_sec,
            {% for c in count_cols %}k._prim_{{ loop.index }},
            {% endfor %}
            {% for rate, comps in rates.items() %}k._small_{{ rate }},
            {% endfor %}
            -- siblings share a parent and a depth; the parent row must itself be published (not primary-suppressed)
            count(*) filter (where k._primary_sec) over (partition by k._parent, k._depth)  as _n_primary,
            count(*) over (partition by k._parent, k._depth)                                as _n_siblings,
            p._node is not null and not p._primary_sec                                      as _parent_published,
            row_number() over (partition by k._parent, k._depth
                               order by case when k._primary_sec then 1 else 0 end,
                                        case when k.{{ sec }} = 0 then 1 else 0 end, k.{{ sec }}, k._node) as _smallest_rank
        from keyed k
        left join keyed p on p._node = k._parent and p._depth = k._depth - 1

    ),

    decided as (

        select
            {% for c in ns.cols %}{{ c }},
            {% endfor %}
            {% for c in count_cols %}_prim_{{ loop.index }},
            {% endfor %}
            {% for rate, comps in rates.items() %}_small_{{ rate }},
            {% endfor %}
            _primary_sec,
            -- exactly one primary-suppressed cell, a published parent, and another cell to hide: hide the next smallest
            (not _primary_sec) and {{ sec }} > 0 and _n_primary = 1 and coalesce(_parent_published, false)
                and _smallest_rank = 1 and _n_siblings > 1 as _secondary
        from grp

    )

    select
        {% for d in dims %}{{ d }},
        {% endfor %}
        {% for c in count_cols %}case when _prim_{{ loop.index }} or _secondary then null else {{ c }} end as {{ c }},
        {% endfor %}
        {% for rate, comps in rates.items() %}case when _small_{{ rate }} or _secondary or _primary_sec
            {%- for c in count_cols %} or _prim_{{ loop.index }}{% endfor %} then null else {{ rate }} end as {{ rate }},
        {% endfor %}
        {% for c in passthrough %}{{ c }},
        {% endfor %}
        case when _secondary then 'SECONDARY'
             when {% for c in count_cols %}_prim_{{ loop.index }}{{ ' or ' if not loop.last }}{% endfor %} then 'PRIMARY'
             else 'NONE' end as suppressed
    from decided
)
{%- endmacro %}
