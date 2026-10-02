{{ config(tags=['phase2']) }}
-- m-probabilities must be proper distributions and cover exactly the feature levels the comparison produces.
-- Returns problems; passes when empty.
with expected(feature, level) as (
    values
        ('first_name','EXACT'),('first_name','NICKNAME'),('first_name','FUZZY_HIGH'),('first_name','FUZZY_LOW'),('first_name','DIFFERENT'),('first_name','MISSING'),
        ('last_name','EXACT'),('last_name','FUZZY_HIGH'),('last_name','FUZZY_LOW'),('last_name','DIFFERENT'),('last_name','MISSING'),
        ('dob','EXACT'),('dob','DAY_MONTH_SWAPPED'),('dob','SAME_YEAR_ONLY'),('dob','YEAR_OFF_BY_ONE'),('dob','DIFFERENT'),('dob','MISSING'),
        ('email','EXACT'),('email','DIFFERENT'),('email','MISSING'),
        ('phone','EXACT'),('phone','DIFFERENT'),('phone','MISSING'),
        ('postal','EXACT'),('postal','PREFIX'),('postal','DIFFERENT'),('postal','MISSING'),
        ('sex','AGREE'),('sex','DISAGREE'),('sex','UNKNOWN'),
        ('context','SAME_ORG_SAME_SEASON'),('context','SAME_SEASON_DIFF_ORG'),('context','DIFF_SEASON')
)
select 'sum_not_1' as problem, feature as detail, sum(m_probability) as value
from {{ ref('match_m_probabilities') }} group by feature having abs(sum(m_probability) - 1) > 1e-9
union all
select 'out_of_range', feature || '.' || level, m_probability
from {{ ref('match_m_probabilities') }} where m_probability <= 0 or m_probability >= 1
union all
select 'level_not_in_comparison', m.feature || '.' || m.level, m.m_probability
from {{ ref('match_m_probabilities') }} m left join expected e using (feature, level) where e.level is null
union all
select 'level_missing_from_seed', e.feature || '.' || e.level, null
from expected e left join {{ ref('match_m_probabilities') }} m using (feature, level) where m.level is null
