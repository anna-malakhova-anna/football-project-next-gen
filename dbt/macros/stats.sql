{#-
  Small statistics helpers in portable SQL (no distribution functions needed from the engine).

  normal_cdf(z)         the standard normal CDF, Abramowitz and Stegun 26.2.17 (absolute error under 8e-8)
  chisq_upper_p(x, df)  the upper-tail p-value of a chi-square statistic x with df degrees of freedom, by the Wilson-Hilferty normal approximation. Approximate for df = 1 or 2
                        (it can be off by a few percent of the p-value there) and very good above; used only to decide "is this association unlikely to be chance", never reported as exact.
-#}
{% macro normal_cdf(z) -%}
(case when ({{ z }}) >= 0 then 1 else 0 end * (1 - 0.3989422804 * exp(-0.5 * ({{ z }}) * ({{ z }})) * (
        0.319381530 * (1 / (1 + 0.2316419 * abs({{ z }}))) - 0.356563782 * power(1 / (1 + 0.2316419 * abs({{ z }})), 2) + 1.781477937 * power(1 / (1 + 0.2316419 * abs({{ z }})), 3)
        - 1.821255978 * power(1 / (1 + 0.2316419 * abs({{ z }})), 4) + 1.330274429 * power(1 / (1 + 0.2316419 * abs({{ z }})), 5)))
 + case when ({{ z }}) < 0 then 1 else 0 end * (0.3989422804 * exp(-0.5 * ({{ z }}) * ({{ z }})) * (
        0.319381530 * (1 / (1 + 0.2316419 * abs({{ z }}))) - 0.356563782 * power(1 / (1 + 0.2316419 * abs({{ z }})), 2) + 1.781477937 * power(1 / (1 + 0.2316419 * abs({{ z }})), 3)
        - 1.821255978 * power(1 / (1 + 0.2316419 * abs({{ z }})), 4) + 1.330274429 * power(1 / (1 + 0.2316419 * abs({{ z }})), 5))))
{%- endmacro %}

{% macro chisq_upper_p(x, df) -%}
case when ({{ df }}) < 1 or ({{ x }}) is null then null
     when ({{ x }}) <= 0 then 1.0
     else 1 - {{ normal_cdf("((power(" ~ x ~ " / " ~ df ~ ", 1.0 / 3) - (1 - 2.0 / (9 * " ~ df ~ "))) / sqrt(2.0 / (9 * " ~ df ~ ")))") }} end
{%- endmacro %}
