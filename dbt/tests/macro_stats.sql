{{ config(tags=['phase5']) }}
-- normal_cdf and chisq_upper_p against known values: Phi(0) = 0.5, Phi(1.96) = 0.975, Phi(-1.96) = 0.025; chi-square upper tail: P(X > 3.841; df 1) = 0.05, P(X > 18.307; df 10) = 0.05,
-- P(X > 31.41; df 20) = 0.05, P(X > 124.34; df 100) = 0.05. The approximation is good to about 0.005 for df >= 10 and within 0.01 at df 1; the tolerances say so.
with t as (

    select 'phi(0)' as name, {{ normal_cdf('0.0') }} as got, 0.5 as want, 1e-6 as tol
    union all select 'phi(1.96)', {{ normal_cdf('1.96') }}, 0.975, 1e-4
    union all select 'phi(-1.96)', {{ normal_cdf('-1.96') }}, 0.025, 1e-4
    union all select 'chisq df1', {{ chisq_upper_p('3.841', '1') }}, 0.05, 0.012
    union all select 'chisq df10', {{ chisq_upper_p('18.307', '10') }}, 0.05, 0.005
    union all select 'chisq df20', {{ chisq_upper_p('31.41', '20') }}, 0.05, 0.005
    union all select 'chisq df100', {{ chisq_upper_p('124.34', '100') }}, 0.05, 0.005
    union all select 'chisq huge', {{ chisq_upper_p('500', '3') }}, 0.0, 1e-6
    union all select 'chisq zero', {{ chisq_upper_p('0', '3') }}, 1.0, 1e-6

)

select name, got, want from t where abs(got - want) > tol
