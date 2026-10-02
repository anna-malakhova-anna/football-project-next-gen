{#-
  pseudonymize(col, salt=none)  ->  sha256(col || salt), 64 hex characters; NULL stays NULL.

  The salt comes from the environment variable FLAG_PSEUDO_SALT. It is never committed; if the variable is unset a
  documented DEV-ONLY default is used so the project runs from a clean clone. A real deployment must set a secret salt
  and keep it out of the repository. Note that dbt writes compiled SQL (with the salt) under dbt/target/, which is
  gitignored; do not publish it.

  A pseudonym is still personal data: it is re-identifiable by combining quasi-identifiers (see ADR-006). It only stops a
  direct join back to participant_id for someone who lacks the salt.

  Snowflake: SHA2(col || salt, 256) (hex), with the salt held in a secret or a masking-policy function rather than in SQL.
-#}
{% macro pseudonymize(col, salt=none) -%}
{%- set s = salt if salt is not none else env_var('FLAG_PSEUDO_SALT', 'dev-only-salt-do-not-use-in-production') -%}
sha256({{ col }} || '{{ s | replace("'", "''") }}')
{%- endmacro %}
