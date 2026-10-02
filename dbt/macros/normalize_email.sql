{#-
  normalize_email(col, fold_gmail=none)
  Lowercase + trim; blank -> NULL. Whitespace/case variants are the only thing normalized by default.

  Gmail dot/plus folding (a.b+x@gmail.com -> ab@gmail.com) is OFF by default (var email_fold_gmail).
  Why: folding is correct for Gmail but only for Gmail; applying it also merges addresses that are
  distinct mailboxes at other providers, and a shared guardian email already links siblings. A wrong
  merge here silently collapses different people, so identity resolution (Phase 2) should opt in
  deliberately and treat folded matches as a weaker signal.
-#}
{% macro normalize_email(col, fold_gmail=none) -%}
{%- set fold = var('email_fold_gmail', false) if fold_gmail is none else fold_gmail -%}
{%- set e -%}nullif(lower(trim({{ col }})), ''){%- endset -%}
{%- if fold -%}
case
    when {{ e }} is null then null
    when split_part({{ e }}, '@', 2) in ('gmail.com', 'googlemail.com')
        then replace(split_part(split_part({{ e }}, '@', 1), '+', 1), '.', '') || '@' || split_part({{ e }}, '@', 2)
    else {{ e }}
end
{%- else -%}
{{ e }}
{%- endif -%}
{%- endmacro %}
