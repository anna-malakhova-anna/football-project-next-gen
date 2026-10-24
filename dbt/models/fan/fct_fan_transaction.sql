-- Transactions net of refunds, one row per delivered-once transaction line, attributed to the canonical fan account (duplicates collapsed). Synthetic currency.
--   signed_amount    a purchase counts +amount, a refund that matches an original counts -amount
--   ORPHAN refunds   a refund whose original_txn_id matches no transaction is NOT revenue and NOT a deduction: it is kept, flagged `is_orphan_refund`, counted in the DQ log, and excluded
--                    (is_in_net = false) so it cannot quietly shave revenue
--   a transaction on an unknown account, with an unknown category or a non-numeric amount is excluded too; nothing is repaired
select
    t.txn_id,
    x.fan_account_id,
    t.txn_ts,
    t.txn_month,
    t.category,
    t.amount,
    t.is_refund,
    t.original_txn_id,
    t.is_orphan_refund,
    not t.is_orphan_refund and 'orphan_transaction' <> all(t.dq_flags) and 'unmapped_txn_category' <> all(t.dq_flags) and 'non_numeric_amount' <> all(t.dq_flags) as is_in_net,
    case
        when t.is_orphan_refund or t.amount is null then 0.0
        when t.is_refund then -t.amount
        else t.amount
    end::decimal(18, 2)                                                     as signed_amount   -- money is exact: a float sum depends on row order, which flipped RFM quintiles between macOS and Linux
from {{ ref('stg_fan_transactions') }} t
join {{ ref('int_fan_account_xref') }} x using (account_id)
where not t.is_duplicate
