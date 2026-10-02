{#-
  suppression_group_violations(relation, dims, count_col)
  An INDEPENDENT re-check of the suppression rules on a published table (it does not call suppress_small_cells), for
  the singular tests on share_exec. Returns problems; no rows means the table obeys the rules:
    UNSUPPRESSED_SMALL_CELL   a count above zero and below k_min that is still published
    LONE_SUPPRESSED_CELL      a group of sibling cells (same parent, same depth) with a published subtotal in which
                              exactly one cell is suppressed, so it could be recovered by subtraction
-#}
{% macro suppression_group_violations(relation, dims, count_col) -%}
{%- set n = dims | length -%}
(
    with r as (

        select
            {% for d in dims %}{{ d }},
            {% endfor %}
            {{ count_col }} as _count,
            {% for i in range(n) %}case when {{ dims[i] }} is not null then 1 else 0 end{{ ' + ' if not loop.last }}{% endfor %} as _depth,
            concat_ws('|', {% for d in dims %}{{ d }}{{ ', ' if not loop.last }}{% endfor %}) as _node
        from {{ relation }}

    ),

    p as (

        select
            _node, _depth, _count,
            {% if n > 1 -%}
            case _depth
                {% for i in range(1, n) %}when {{ i + 1 }} then concat_ws('|', {% for j in range(i) %}{{ dims[j] }}{{ ', ' if not loop.last }}{% endfor %})
                {% endfor %}
                else null
            end
            {%- else -%}
            cast(null as varchar)
            {%- endif %} as _parent
        from r

    ),

    groups as (

        select
            c._parent, c._depth,
            count(*) as n_cells,
            count(*) filter (where c._count is null) as n_suppressed,
            bool_or(par._count is not null) as parent_published
        from p c
        left join p par on par._node = c._parent and par._depth = c._depth - 1
        where c._parent is not null
        group by c._parent, c._depth

    )

    select 'UNSUPPRESSED_SMALL_CELL' as problem, _node as detail, _count as value
    from p where _count > 0 and _count < {{ privacy_param('k_min') }}
    union all
    select 'LONE_SUPPRESSED_CELL', _parent || ' @depth ' || _depth, n_suppressed
    from groups where parent_published and n_suppressed = 1 and n_cells > 1
)
{%- endmacro %}
