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
baselines/<tree-id>.bundle                  a benchmark input's staged workspace, stored once
workspaces/<candidate-hash>/<run-id>/       a record's graded workspace, as a diff from its baseline
exclusions/<candidate-hash>/<run-id>.json   why an analysis leaves a record out
karn/                                       the Karn recipes that build the candidates
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
3. **Heavy artifacts never enter git, except graded workspaces as diffs.**
   Transcripts, logs, workspace snapshots and per-card trees live elsewhere;
   `manifest.json` carries *pointers* only. Each record's graded workspace is
   kept under `workspaces/` as a diff from a shared baseline (below).
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

## Schema 2: Karn observations

New Karn runs use `schema_version: 2` with candidate scheme `karn-v4`.
The candidate object records `definition_version: 4`, `definition_id`, `definition_digest`, immutable `image`, and resolved `image_id`.
Its directory key is the SHA-256 hex digest of that whole candidate object's canonical UTF-8 JSON (sorted keys, minimal separators, non-ASCII preserved).
The manifest contains `run_id`, `candidate`, `candidate_hash`, `benchmark`, `budget_seconds`, `run_metadata`, and `artifact_pointers`; it contains no mode, proposal, or leaderboard eligibility field.

`run_metadata` preserves the full selected definition, benchmark input identity, execution outcome, measurement observations, and grading-source provenance.
Measurements retain response/tool components, token usage, versioned API-equivalent pricing, and completeness reasons.
The three existing score-dimension names remain; an absent dimension uses `evaluated: false`, null counts/pass rate, and `missing_reasons`.
Coverage distinguishes the complete reference population from cards with executed audited cases.
A snapshot fallback names its selected source while retaining the final workspace separately.
Host grading inputs have content fingerprints in `run_metadata.grading_inputs`.
A later recovery observation can have its own record id while `recovery_of` and `execution_run_id` link it to the original model execution; the prior record remains unchanged, and the derived index exposes that link.

The reader and derived index preserve both schemas without changing historical identities or interpreting new data through historical publication rules.
The remaining schema details below describe schema 1 only.

## Workspace archives

`workspaces/<candidate-hash>/<run-id>/` holds two write-once files for a record
with a graded workspace: `workspace.patch`, a `git diff --binary --full-index`
from the benchmark input's staged baseline to the tree grading used, and
`workspace.json`:

| Field | Meaning |
| --- | --- |
| `format_version` | `1` |
| `run_id`, `candidate_hash` | The record it belongs to |
| `baseline` | `tree` and `commit` ids of the staged workspace, its `bundle` path under `baselines/`, and its `content_digest` (the record's `benchmark_input.workspace_digest`) |
| `graded` | `source` (the record's `grading_source.selected`), the `tree` id grading used, and its `content_digest` (the digest the record's `grading_source` states for that copy) |
| `patch` | `path`, `sha256`, `bytes`, `files_changed` |
| `grading_copy_omits` | What grading's copy of a workspace leaves out: caches, `*.pyc`, symlinks |
| `archived_at` | When it was written |

`baselines/<tree-id>.bundle` holds one commit, `refs/baselines/base`, whose tree
is the baseline. Rebuild a workspace only with the bench (`silverquillm regrade`
does it for you): it applies the patch in a scratch repository with git
plumbing, and refuses the result unless its tree id and content digest match
`workspace.json` and the record. Runs write their own archive; `silverquillm
results archive` backfills records on the host that holds their run artifacts.

## Exclusions

An analysis leaves a record out only through
`exclusions/<candidate-hash>/<run-id>.json`, written once and never by editing
the record:

| Field | Meaning |
| --- | --- |
| `format_version` | `1` |
| `run_id`, `candidate_hash` | The excluded record |
| `reason` | `subagents_used`, `subagents_uncounted`, `never_executed`, `host_failed`, `superseded`, `benchmark_defect`, `pilot` or `other` |
| `note` | Why, checkably |
| `source` | `rule` (written by the bench on an observed fact) or `operator` |
| `superseded_by` | The replacing record's run id, only for `superseded` |
| `excluded_by`, `excluded_at` | Who and when |

Rules exclude a record for `host_failed` (execution status), `never_executed`
(zero observed agent turns), `subagents_used` (subagent threads observed) and
`subagents_uncounted` (a populated measurement object without a
`subagent_threads` count). An unknown measurement never excludes: absent, null or
empty measurements, and a present but unknown turn or thread count, leave the
record in. Operators add the rest with `silverquillm results exclude`. To include
a record again, delete its file.

Every analysis applies these files and no private filter: aggregate the records
without an exclusion, and list the excluded ones with their reasons beneath the
table (`silverquillm results exclusions`). `silverquillm regrade` does the same:
it grades excluded records too, but leaves them out of its comparison and lists
them under `excluded` in its summary. `silverquillm results check` reports
records a rule excludes that have no file, and files without a record.

## Building candidates and provenance

Every host builds and runs the same way, so a record traces to committed
sources:

1. Commit and push a recipe under `karn/constructs/<label>` before building it.
2. `karn build <this repo>/karn/constructs/<label> --out <dir>` from the
   committed tree, never `--worktree`; the image's `karn.config.revision`
   label then names the recipe commit.
3. Run bench code from a pushed `main` commit with no uncommitted tracked
   change and no untracked file under `silverquillm/` or `benchmarks/`.
4. Set `SILVERQUILLM_HOST_LABEL` on each host.
5. Use one subscription on one host at a time.

The bench refuses a run that breaks 2 or 3 unless the operator passes
`--allow-dirty`. Every new schema 2 record carries `run_metadata.provenance`:
`host_label` and its `host_label_source`, `bench` and `benchmark_root` (each
`commit` and `dirty`), `recipe_revision`, `allow_dirty`, and the
`dirty_reasons` that were overridden. The grader image is in
`grading_isolation.grader_image_id`.

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

No publication path exists for records in this repo.
The bench's historical publish script, which copied schema 1 `manifest.json` and `scores.json` into a public `published/` tree, was removed with Candidate Bundle execution; nothing was ever published through it.
Records here are never edited by any bench command.

## Vocabulary

Terms follow the bench repo's `CONTEXT.md`: **Benchmark Run** (one container
session consuming a benchmark's entire problem set), **Candidate Bundle** (the
self-contained artifact a candidate is exchanged as), **Resume Leg** (a run with
`resumed_from` set), **Audited Eval** (the three dimensions above). "Workload"
is retired.
