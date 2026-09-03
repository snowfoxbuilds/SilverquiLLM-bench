Status: DRAFT

Last updated: 2026-09-03

# Benchmark Candidates

The bench-side lifecycle of a Benchmark Candidate: how a candidate is promoted from the operator's private Config Repo into the public `candidates/` tree, how runs of it are queued and executed by the batch scheduler, and how its results are published.

## Context

Issue #39 rules that a Benchmark Candidate **is** a TheOzolith worker-type definition, exchanged as a Candidate Bundle whose identity the bench recomputes and never trusts ([BENCH-CONTRACT.md](BENCH-CONTRACT.md) owns the bundle format, the identity spec, and the Run Contract; `silverquillm.candidate` is the bench's ingestion). Around that contract the bench owns three surfaces of its own (#39 §§4–5): the curated public set and its promote gate, the file-backed batch queue with its single-writer scheduler, and the publish gate that ports results into the public tree. Nothing here is load-bearing for the substrate — it learns nothing about batches, promotion, or publishing.

## Design

### The curated candidates tree

`candidates/` is the public, curated set of Benchmark Candidates this repo ships — flat and deduplicating, one directory per identity:

```
candidates/<slug>--<hash8>/
  README.md                        what the candidate is and what it varies
  source/worker-types/<type>.toml  the definition the bundle was exported from, base pinned by digest
  source/knowledge/<name>/         the referenced knowledge SOURCE tree (when the candidate bakes one)
  source/policy/<name>/            the referenced Agent Policy tree (when the candidate bakes one)
  bundle/                          the Candidate Bundle, verified as-is on every run
```

`<hash8>` is the first eight characters of the Candidate Hash recomputed from `bundle/` (CONTEXT.md → Candidate Hash). The directory name is a recorded value: `silverquillm run --candidate` and the platform test `tests/test_reference_candidates.py` recompute the identity on every run and refuse a directory whose suffix disagrees with its bundle. The platform test holds every checked-in candidate to the same bar: it ingests, carries its recomputed hash8, holds secret slot *names* only, documents its identity in a completed README, re-exports byte for byte from `source/` with no registry access, and — when it bakes knowledge — vendors a source tree that carries its publishable declaration. The vanilla Reference Candidates additionally vary nothing.

### Promotion — vendor-at-promote is strict

`scripts/promote_candidate.py <config-repo> <worker-type> [--slug NAME] [--candidates-dir DIR] [--docker-config DIR] [--dry-run]` copies one definition from the operator's private Config Repo (the-ozolith ADR-0048 shape: `worker-types/` + `knowledge/` + `policy/`) into `candidates/`. It never runs git: the operator reviews the new directory and commits it, and that commit is the approval stamp.

| Step | Rule |
| --- | --- |
| Publishability gate | A knowledge tree the definition references (`knowledge = "knowledge/<name>"`) must exist in the Config Repo **and** carry a regular file named `PUBLISHABLE` at its root — the operator's explicit declaration (its text is the basis, e.g. the license). TheOzolith's knowledge loader ignores the file and the compiled tree never contains it, so the marker moves no pin and no identity. A missing tree or a missing marker is a hard refusal naming the rule: **knowledge that cannot be published means the candidate cannot be promoted and its results cannot be published**. A referenced Agent Policy tree must exist (it is vendored the same way). |
| Export | The bundle is exported by TheOzolith's own tooling (`theozolith_control.candidate.export_candidate`) into a private staging directory beside the destination, then ingested through the bench's own path (`load_candidate_bundle`: verifier, recomputed identity, secret-value refusal). A private base tag resolves through `--docker-config`; the credential never enters the bundle. |
| Name | `candidates/<slug>--<hash8>/`, slug defaulting to the worker-type name. |
| Dedup by identity | The same identity already promoted under this name is a no-op (a later export with a new `exported_at` is the same candidate). The same identity under another slug is a refusal naming the existing directory. An existing directory under this name whose bundle does not verify or does not recompute to this identity is a refusal — it is never touched. |
| Vendored source | The definition is copied with its top-level `base` pinned to the digest the export resolved when the source carried the tag only (the one edit; a digest-pinned source is copied verbatim). The referenced knowledge and policy source trees are copied whole — regular files and directories only; symlinks and special files refuse; `.git`, `__pycache__`, `.DS_Store` and bytecode are left out. |
| Reproducibility proof | Before anything is published, `source/` is re-exported with the recorded `exported_at` and must reproduce `bundle/` byte for byte; an irreproducible copy is refused. |
| README stub | Written with the identity table, provenance, and `TODO(promote)` placeholders for what the candidate varies and where the base digest came from. The platform test refuses a checked-in README that still carries the placeholder. |
| Atomicity | Every check runs in staging; the candidate directory appears through one rename at the end. A refusal leaves `candidates/` untouched. |

### The batch queue and the scheduler

The queue is the directory `batches/`. A **Batch** is one file `batches/<id>.toml` — desired state, authored and edited in `$EDITOR`, never written by the scheduler:

```toml
not_before = 2026-09-04T02:00:00Z      # optional; RFC 3339 with an offset

[[runs]]
candidate = "candidates/vanilla-claude--4e8b75b6"   # a path, or a candidates/ entry name
mode = "basic"
benchmark = "smoke"
budget_seconds = 14400
```

Exactly these keys, strictly: an unknown key, a naive `not_before`, or a non-positive budget makes the file malformed. A malformed batch is skipped loudly (reported once per file version to the scheduler log) and surfaced by `queue ls`.

`silverquillm scheduler [--once] [--poll-seconds N] [--results-repo …] [--container-user …]` is the single-writer loop:

| Rule | Behavior |
| --- | --- |
| Single writer | `batches/.scheduler.lock` is held with `flock` for the scheduler's life; a second instance refuses to start and names the holder (pid, host, since). The kernel drops the lock with the process, so a crash never leaves a stale lock. A run still marked `running` when a scheduler starts is marked `failed` at startup. |
| Order | Batch files are scanned in name order; run specs are consumed in file order; one run executes at a time. At every step the scheduler takes the first due batch (`not_before` absent or passed) with an unconsumed entry, so batches execute serially in name order and an undue batch is skipped until due. |
| Re-read before each run | The Nth started run of a batch is whatever the file's Nth `[[runs]]` entry is when it starts. Edits to entries already started change nothing (the state records what ran); edits to later entries, including appended ones, take effect; a file that shrinks below the cursor simply has no more work (and resumes at the cursor if entries are appended later). |
| Identity at run start | The candidate ref is resolved (absolute path, path relative to the bench repo, or a bare `candidates/` entry name) and its identity recomputed by `load_candidate_bundle` when the run starts, never at authoring time. The state records that identity and Candidate Hash; the executor runs that verified bundle, so the RunRecord carries the same recomputation. Editing a candidate between scheduling and execution is legal — results record what actually ran. |
| Execution | The bundle run path — `silverquillm.contract.drive_contract_run` over the Docker session factory — exactly what `silverquillm run --candidate` does, with the same run naming (`<benchmark>-<candidate-dir>-<timestamp>` under `runs/<candidate-dir>/`). |
| Failure continues the batch | A run that fails — an unresolvable spec (missing candidate, unknown mode or benchmark, a bundle that does not verify), a classified driver failure, or an executor exception — is recorded `failed` with its reason and the batch continues with the next entry (#66: #39 gives no abort-on-fail rule; a batch is a best-effort serial list, not a transaction). |

Observed state lives beside the queue in `batches/state/<id>.json` (scheduler-owned, gitignored, schema-versioned, written atomically after every transition): one entry per *started* run — index, the spec as consumed, `running` → `done` / `failed`, run id and run dir, the resolved identity and Candidate Hash, timestamps, outcome summary, error. The number of entries is the batch's cursor.

`silverquillm queue ls` prints a one-shot table — every batch, its `not_before` and whether it is due, per-run specs and states (started runs from the state file, pending ones from the file), malformed files, and whether a scheduler holds the lock. `silverquillm top [--interval N]` redraws the same view in the alternate screen until `q`. Both are read-only; editing stays `$EDITOR`-native on batch files.

### Publishing — a porter with two checks, never a librarian

`scripts/publish_results.py --results-repo <clone> --dest published/<subdir> RUN_ID… [--candidates-dir DIR] [--allow-invalid] [--dry-run]` copies the named Run Records (`manifest.json` + `scores.json`, byte for byte) from the private Results Repo into the destination. It never commits: the operator reviews the staged diff and commits, and that commit is the approval stamp.

| Check | Outcome |
| --- | --- |
| Traceability | **Hard refusal.** The run's candidate identity must exist under `candidates/` as `<slug>--<hash8>` and verify by recomputation: the checked-in bundle is ingested and its Candidate Hash and identity triple must equal the record's. An absent candidate ("promote it first"), a bundle that fails verification, an identity mismatch (both values printed), or a `legacy` identity (which has no bundle) refuses. When the Results Repo holds the vendored copy at `results/<hash>/candidate/` it is re-verified too. |
| Validity | **Warning.** `leaderboard_valid: false` — a Resume Leg, an ineligible benchmark, an unevaluated or gate-failed run — is reported with its reasons and refuses unless `--allow-invalid` is passed. A published-but-invalid record carries the flag, and leaderboard tooling filters on it mechanically, so it can never contaminate a leaderboard. |

Every run is checked before the first file is staged (all or nothing); a byte-identical record already at the destination is skipped; a differing one is a conflict that refuses. Discovery of published results goes through manifests only, never a path convention: a directory anywhere under `published/` is a published run iff it holds `manifest.json` beside `scores.json` and the pair re-proves as a Run Record whose `run_id` is the directory's name (`publish_results.iter_published_records`). How `published/` is organized — per blog post, per experiment — is the operator's, by hand.

### What stays manual

- Completing the promoted README (what the candidate varies, where the base digest came from) and committing the directory.
- Authoring and editing batch files; deciding when a batch is due.
- Choosing which runs to publish, the destination, and committing the staged files.
- Leaderboard and aggregate derivation over `published/` is future work; whatever derives it filters on `leaderboard_valid`.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-008](../adr/ADR-008-resume-legs-are-independent-benchmark-runs.md) | Resume Legs Are Independent Benchmark Runs — why a Resume Leg is never leaderboard-valid, and so publishes only with `--allow-invalid` |
| [ADR-011](../adr/ADR-011-three-tier-benchmark-locking.md) | Three-Tier Benchmark Locking — Released → Benchmarking retracts published scores |
