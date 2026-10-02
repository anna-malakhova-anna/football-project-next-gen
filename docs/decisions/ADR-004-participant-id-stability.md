# ADR-004: Participant ID stability

- **Status:** Accepted (Phase 2). The simple scheme is built; the production design is described, not built.
- **Context:** `dim_participant` needs a key that downstream tables can join on. Identity resolution can change when new
  data or a steward decision links or unlinks records, so the key has to be defined with that in mind.

## Decision

`participant_id = 'P-' || upper(left(md5(min source_record_id in the cluster), 12))` (macro `participant_id`).

- **Deterministic.** The same data and the same matcher give the same ids on every run. `make id-stability` rebuilds
  the identity and mart models from scratch and compares: 6,002 participants and 14,289 registration mappings were
  identical across a rebuild.
- **Independent of row order and of cluster id.** It uses the smallest `source_record_id` (a source-assigned string),
  not a surrogate counter.
- **Visibly distinct from ground truth.** True-person ids in the evaluation schema are `P-` plus 6 digits; participant
  ids are `P-` plus 12 hex characters.

## When it changes (and why that is a limitation)

The id is a function of the cluster's smallest record, so it changes whenever that minimum changes:

| Event | Effect |
|---|---|
| Two clusters merge (a new link, a steward MATCH) | One of the two ids disappears: the merged cluster takes the id of whichever side holds the smaller record |
| A cluster splits (a steward NO_MATCH, a changed threshold) | The part holding the old minimum keeps the id; the other part gets a new one |
| A new registration with an earlier `source_record_id` joins | The whole cluster is renamed |
| A matcher change (`fs` to `rules`) | Many ids change |

Anything that stored a `participant_id` (a report, a consent record, a fan-engagement join) would silently point at a
different person or at nothing. That is acceptable for a rebuilt-from-scratch analytical model and unacceptable for
a system of record.

## Production design (described, not built)

Persist identity instead of recomputing it. Three tables:

| Table | Key columns | Purpose |
|---|---|---|
| `participant_registry` | `participant_id` (surrogate, assigned once), `status` (ACTIVE, MERGED, RETIRED), `merged_into_id`, `created_at` | The permanent id; never reused |
| `participant_id_history` | `participant_id`, `event` (CREATE, MERGE, SPLIT, RETIRE), `related_ids`, `cluster_signature`, `reason` (matcher run, steward id), `effective_at` | Audit trail of every merge and split |
| `registration_assignment` | `registration_key`, `participant_id`, `valid_from`, `valid_to` | Which participant a registration belonged to, over time |

Rules: a merge keeps the **oldest** id and marks the other `MERGED` with a pointer; a split keeps the id for the
**largest** part and mints new ids for the rest; an id is never recycled, and consumers resolve `MERGED` ids through
`merged_into_id`. A run matches its clusters to the previous run's by overlap of registration keys to decide which id
survives. Because consent and fan data would hang off this key, a split or merge also has to raise a review task for
whatever consent was attached to the old id.

## Consequences

The simple scheme is correct for what Phase 2 and Phase 3 need (one deterministic snapshot of who the participants are)
and is easy to test. It must not be used as a durable identifier outside this project.
