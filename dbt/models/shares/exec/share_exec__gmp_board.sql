{{ config(tags=['phase7']) }}
-- EXEC share (DP6 port global_priorities, spec section 9): the market Now/Next/Later board, one card per program market: lane, action, gate and its
-- computed progress, and the priority with its four dimension scores (DRAFT until Anna sets them, score_status says which). A planning view across
-- regimes: it carries nothing beyond the status, grade and clubs already in the regime ports, so it is one port (ADR-029).
select
    b.country_code, b.country_name, b.lane, b.action, b.gate_kind, b.target, b.target_value, b.current_value, b.gate_status, b.bar_fill_pct,
    b.status, b.counting_grade, b.clubs_with_rights,
    p.value_to_goals, p.feasibility_today, p.data_readiness, p.privacy_risk, b.priority_score, b.priority_rank, b.score_status, b.plan_status, b.rationale
from {{ ref('mart_gmp_board') }} b
join {{ ref('mart_gmp_priority') }} p using (country_code)
order by case b.lane when 'NOW' then 1 when 'NEXT' then 2 when 'LATER' then 3 else 4 end, b.priority_rank
