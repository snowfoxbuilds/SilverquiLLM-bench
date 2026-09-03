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
results/<candidate-hash>/candidate/         the vendored Candidate Bundle (ozolith-v1 only)
results/<candidate-hash>/<run-id>/manifest.json
results/<candidate-hash>/<run-id>/scores.json
```

- `<candidate-hash>` is the directory key derived from the run's candidate
  identity (instruction-independent). For the `legacy` identity scheme it is
  the legacy image directory name **unchanged** — legacy names must already be
  safe path segments (`[A-Za-z0-9._-]`, no leading dot), and nothing is ever
  sanitized, so two distinct images can never collide into one key. For
  `ozolith-v1` it is the SHA-256 hex digest of the compact canonical JSON
  (sorted keys, `,`/`:` separators) of the whole identity triple
  `{"adapter": …, "base_digest": "sha256:…", "instruction_hash": …}` — the
  triple, not the instruction hash alone, because TheOzolith's canonical
  identity omits the adapter name. The bench recomputes it from the bundle on
  every run; the first eight characters are the `<slug>--<hash8>` suffix of a
  checked-in candidate in the bench repo's `candidates/`.
- `candidate/` (ozolith-v1 candidates only) is the vendored Candidate Bundle
  exactly as verified — `candidate.json`, `Dockerfile`, and the compiled
  knowledge / baked policy trees when the candidate bakes them. Written once,
  on the candidate's first run, and verified at write time (TheOzolith's
  verifier must recompute the copy to this directory's hash); never edited.
  Later runs re-verify it and skip the write; a copy that no longer recomputes
  to its directory is refused, never repaired. It is never a run: the reader
  and the index skip the name. Hash = authority; copy = resolution.
- `<run-id>` is the Benchmark Run's id (for migrated legacy runs, the original
  run directory name, e.g. `sos-cc-opus-48-bare-2026-05-30T04-02`; for
  Contract Runs `<benchmark>-<candidate-dir>-<timestamp>`).

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
4. **Identity is never trusted from a recorded value.** An `ozolith-v1`
   identity exists only as the output of recomputation: the bench verified
   the Candidate Bundle through TheOzolith's verifier (`bundle_format_version`
   2 / `identity_spec_version` 2), recomputed the triple from bundle bytes,
   and refused any bundle whose recorded identity disagreed — so it records
   `verified: true`, and an `ozolith-v1` identity with anything else is
   malformed. A `legacy` identity is a label, not a proof, and records
   `verified: false`, always. The bench's reader enforces both, and rejects a
   record whose directory name, `run_id`, `candidate`, and `candidate_hash`
   disagree rather than attributing it to anyone.
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
| `candidate` | object | Candidate identity: `scheme` (`legacy` or `ozolith-v1`), `base_image_digest`, `instruction_hash`, `adapter_identity`, `verified`. Under `ozolith-v1` they are TheOzolith's identity triple — the base image digest (`sha256:…`), the instruction hash (sha256 over the canonical identity: base, materialized setup, knowledge ref + pin, conditional knowledge target / policy keys) and the adapter name (opaque: claude, codex, or any adapter the substrate maps — the bench keeps no allowlist) — recomputed by the verifier, `verified: true`. Under `legacy` all three hash fields carry `legacy:<image-dir>` — the Docker image was the whole agent configuration, so the tuple does not decompose — and `verified` is `false`. |
| `candidate_hash` | string | The `results/<candidate-hash>/` key; equals the parent directory name. |
| `mode` | string | Benchmark Mode of the run spec (`basic`, `planned`, …). `legacy` for every migrated run: the legacy lineage encoded variants in image names, which is a different concept from the mode registry, so nothing was parsed — the image dir in the identity is the discriminator. |
| `benchmark` | string | Benchmark id (`sos`, `smoke`, `hob-medium`, …). One benchmark = one whole problem set. |
| `budget_seconds` | int | The run's time budget. |
| `leaderboard_valid` | bool | Derived by one rule (below); tooling filters on it mechanically. |
| `resumed_from` | string or null | Prior leg's run id for a Resume Leg; null for a fresh run. |
| `proposal_status` | string or null | What the contract driver recorded about `output/proposal.json` (`applied`, `missing`, `invalid`). Null for legacy runs, which had no proposal. |
| `run_metadata` | object | Metadata only, never identity-bearing: `run_date`, versions, `run_status`, `wall_clock_seconds`, notes. Migrated runs carry `docker_image`, `image_dir`, `harness_version`, `card_filter`, `scored_card_count`, `budget_seconds_source`, `migrated_from`, and a `validity_note` when `leaderboard_valid` is false. Contract Runs carry the whole `contract_run.json` evidence: the candidate's `adapter`, `worker_type`, `model`, `effort`, `product_version`, `exported_at`, `tag`, `path`; the built `image` (`tag`, `id`); the bound/unbound secret slot *names* (`secret_slots`); `phase`, `phases_run`, classified `failure`/`failures`, `warnings`, `container`, `agent_outcome`, the harness-authored `harness_status`, `transcript` summary, `gate`, `proposal_errors`, `commit_sha`, `timing`, the pinned `worker` and `contract_packages` and the three contract version keys. |
| `artifact_pointers` | array | `{"kind", "location"}` references to heavy artifacts. A `legacy-tree` location is canonical and identity-bound: exactly `docker/<image-dir>/validated_results/<run-id>/` for the record's own candidate and run id, relative to the bench repo root — never absolute, never another candidate's path; the bench validates this on write, on read, and again before following the pointer. After the legacy trees are deleted (bench issue #66) these locations resolve only through the bench repo's git history. Contract Runs carry `run-artifacts` (the run directory: job dir, driver repository, `workspace_final/`, trusted input) and `contract-run-evidence` (its `contract_run.json`) on the run host, plus `candidate-bundle` — `results/<candidate-hash>/candidate/`, relative to this repo — when the vendored copy was written or re-verified. |

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

## Publishing

Records leave this repo only through the bench repo's publish script
(`scripts/publish_results.py`, which never commits): `manifest.json` and
`scores.json` are copied byte for byte into the bench repo's public
`published/` tree — transactionally, so the requested set appears whole or
not at all, and a published record is never overwritten — after the run's
candidate identity is traced to a checked-in `candidates/<slug>--<hash8>/`
that verifies by recomputation (a hard refusal otherwise) and its
`leaderboard_valid` flag is reported (`false` publishes only on explicit
override, and leaderboard tooling filters on the flag). The vendored copy
under `results/<candidate-hash>/candidate/`, when present, is re-verified at
publish time. Nothing here is ever edited by publication.

## Vocabulary

Terms follow the bench repo's `CONTEXT.md`: **Benchmark Run** (one container
session consuming a benchmark's entire problem set), **Candidate Bundle** (the
self-contained artifact a candidate is exchanged as), **Resume Leg** (a run with
`resumed_from` set), **Audited Eval** (the three dimensions above). "Workload"
is retired.
