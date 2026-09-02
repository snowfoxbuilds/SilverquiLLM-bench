# SilverquiLLM results repo

This repository is the **private, git-as-truth home for SilverquiLLM benchmark
results**. It is self-contained: an analysis agent needs nothing outside this
repo to read, filter, and aggregate runs. The bench repo
(`snowfoxbuilds/SilverquiLLM-bench`) writes records here through
`silverquillm.results_repo`; nothing else writes.

## Layout

```
AGENTS.md                                   this file — the schema
runs.jsonl                                  derived index (see "Index is derived")
results/<candidate-hash>/<run-id>/manifest.json
results/<candidate-hash>/<run-id>/scores.json
```

- `<candidate-hash>` is the directory key derived from the run's candidate
  identity (instruction-independent). For the `legacy` identity scheme it is
  the sanitized legacy image directory name; for `ozolith-v1` it is the
  identity hash defined by the-ozolith identity-hash spec.
- `<run-id>` is the Benchmark Run's id (for migrated legacy runs, the original
  run directory name, e.g. `sos-cc-opus-48-bare-2026-05-30T04-02`).

## Rules

1. **Records are immutable.** A `<run-id>` directory is written once, atomically,
   and never edited. Corrections are new runs, not edits. The writer refuses to
   overwrite.
2. **Index is derived.** `runs.jsonl` is regenerated from the tree
   (`python scripts/rebuild_results_index.py --results-repo <path>` in the bench
   repo). It is never hand-edited and never authoritative: if the index and the
   tree disagree, the tree wins — rebuild the index.
3. **Heavy artifacts never enter git.** Transcripts, logs, workspace snapshots
   and per-card trees live elsewhere; `manifest.json` carries *pointers* only.
4. **Identity is never trusted from a recorded value.** `candidate.verified` is
   `false` until the bench recomputes identity from a Candidate Bundle. Treat
   `verified: false` identities as labels, not proofs.
5. **`benchmark`, never `workload`.** One benchmark is one whole problem set; a
   run always consumes the entire set. The retired "workload" (card-subset) term
   does not appear in this repo.

## `manifest.json`

```json
{
  "schema_version": 1,
  "run_id": "sos-cc-opus-48-bare-2026-05-30T04-02",
  "candidate": {
    "scheme": "legacy",
    "base_image_digest": "legacy:cc-opus-48-bare",
    "instruction_hash": "legacy:cc-opus-48-bare",
    "adapter_identity": "legacy:cc-opus-48-bare",
    "verified": false
  },
  "candidate_hash": "cc-opus-48-bare",
  "mode": "legacy",
  "benchmark": "sos",
  "budget_seconds": 360000,
  "leaderboard_valid": true,
  "resumed_from": null,
  "proposal_status": null,
  "run_metadata": { "run_date": "2026-05-30T07:49:12Z", "...": "metadata only" },
  "artifact_pointers": [
    { "kind": "legacy-tree", "location": "docker/cc-opus-48-bare/validated_results/sos-cc-opus-48-bare-2026-05-30T04-02/" }
  ]
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | int | Always `1` for this schema. |
| `run_id` | string | The Benchmark Run id; equals the directory name. |
| `candidate` | object | Candidate identity: `scheme` (`legacy` or `ozolith-v1`), `base_image_digest`, `instruction_hash`, `adapter_identity`, `verified`. Under `legacy` all three hash fields carry `legacy:<image-dir>` — the Docker image was the whole agent configuration, so the tuple does not decompose. |
| `candidate_hash` | string | The `results/<candidate-hash>/` key; equals the parent directory name. |
| `mode` | string | Benchmark Mode of the run spec (`basic`, `planned`, …). `legacy` for every migrated run: the legacy lineage encoded variants in image names, which is a different concept from the mode registry, so nothing was parsed — the image dir in the identity is the discriminator. |
| `benchmark` | string | Benchmark id (`sos`, `smoke`, `hob-medium`, …). One benchmark = one whole problem set. |
| `budget_seconds` | int | The run's time budget. |
| `leaderboard_valid` | bool | Derived by one rule (below); tooling filters on it mechanically. |
| `resumed_from` | string or null | Prior leg's run id for a Resume Leg; null for a fresh run. |
| `proposal_status` | string or null | What the contract driver recorded about `output/proposal.json` (`applied`, `missing`, `invalid`). Null for legacy runs, which had no proposal. |
| `run_metadata` | object | Metadata only, never identity-bearing: `run_date`, versions, `run_status`, `wall_clock_seconds`, notes. Migrated runs carry `docker_image`, `image_dir`, `harness_version`, `card_filter`, `scored_card_count`, `budget_seconds_source`, `migrated_from`, and a `validity_note` when `leaderboard_valid` is false. |
| `artifact_pointers` | array | `{"kind", "location"}` references to heavy artifacts. `legacy-tree` locations are paths relative to the bench repo root; after the legacy trees are deleted (bench issue #66) they resolve only through the bench repo's git history. |

### `leaderboard_valid`

`false` when any of these holds, otherwise `true`:

1. the benchmark's `config.json` says `leaderboard.eligible: false` (the smoke
   benchmark is never leaderboard-published);
2. `resumed_from` is set (Resume Legs inherit prior-leg workspace state and are
   not head-to-head comparable);
3. a card filter was present and differs from the benchmark's card set after
   integer normalization of collector numbers (`"1"` and `"001"` are the same
   card);
4. the scored card set differs from the benchmark's card set.

When false, migrated records explain why in `run_metadata.validity_note`.

## `scores.json`

Exactly three keys — the audited dimensions under benchmark-neutral names, each
holding the bench's `run_summary.json` block for that dimension unchanged:

```json
{
  "card_correctness": { "audited_pass_rate": 0.8193, "card_pass_rate": 0.3, "cards_completed": 10, "cards_no_output": 0, "cards_timed_out": 0 },
  "fdn_regression":   { "fdn_test_pass_rate": 1.0, "fdn_card_pass_rate": 0.6364 },
  "engine_regression": { "engine_test_pass_rate": 1.0, "engine_churn_lines": 216 }
}
```

`card_correctness` is the target-set dimension (SOS card correctness for `sos`,
HOB card correctness for the HOB benchmarks). A migrated SOS record, a smoke
record and a HOB record all have this shape.

## `runs.jsonl`

One JSON object per line, sorted by `(candidate_hash, run_id)`, keys sorted:
`candidate_hash`, `run_id`, `benchmark`, `mode`, `leaderboard_valid`, `run_date`.
Rebuild it after any change to `results/`.

## Vocabulary

Terms follow the bench repo's `CONTEXT.md`: **Benchmark Run** (one container
session consuming a benchmark's entire problem set), **Candidate Bundle** (the
self-contained artifact a candidate is exchanged as), **Resume Leg** (a run with
`resumed_from` set), **Audited Eval** (the three dimensions above). "Workload"
is retired.
