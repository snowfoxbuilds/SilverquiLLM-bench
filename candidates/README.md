# Candidates

The public, curated set of Benchmark Candidates this repo ships (issue #39 §4,
#65). A Benchmark Candidate **is** a TheOzolith worker-type definition; it
enters the bench as a **Candidate Bundle** — the self-contained export
`theozolith candidate export` writes (`candidate.json` + generated
`Dockerfile` + compiled knowledge tree + baked policy tree; secret slot
*names* only). `silverquillm run --candidate <path>` accepts nothing else
(CONTEXT.md → Candidate Bundle; `docs/specs/BENCH-CONTRACT.md`).

## Layout

```
candidates/
  README.md                          this file
  <slug>--<hash8>/                   one candidate; flat, deduplicating
    README.md                        what the candidate is and what it varies
    source/worker-types/<slug>.toml  the exact definition the bundle was exported from
    bundle/                          the Candidate Bundle (verified as-is)
      candidate.json
      Dockerfile
      knowledge/ · policy/           only when the candidate bakes them
```

`<hash8>` is the first eight characters of the bench's **candidate hash**:
the SHA-256 of the canonical JSON of the identity triple
`{"adapter", "base_digest", "instruction_hash"}` that TheOzolith's verifier
recomputes from the bundle bytes (`silverquillm.results_repo.candidate_hash`;
the same key names `results/<candidate-hash>/` in the results repo). The name
is a **recorded value**: the bench recomputes the identity on every run and on
every test run, and a directory whose suffix disagrees with its bundle is a
hard refusal. The README and `source/` sit beside `bundle/`, never inside it —
the bundle's layout allowlist admits nothing but the bundle.

## Run one

```bash
silverquillm run --candidate candidates/vanilla-claude--4e8b75b6 \
  --benchmark smoke --timeout 3600 [--mode basic|planned] [--results-repo <clone>]
```

The bench verifies the bundle through `theozolith_control.candidate.verify_bundle`
(recomputed knowledge/policy pins, materialized setup and instruction hash,
Dockerfile byte-matched against the production codegen, allowlisted layout),
refuses any secret value, builds the derived image through the verified
standalone build (`theozolith candidate build` semantics: private snapshot,
full verification, `docker build`, deterministic tag), launches it by image ID
with the in-image harness as PID 1, and records the run under the recomputed
identity. The bundle's `secret_slots` name the environment variables the bench
binds from its own environment (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, …).

## The reference candidates

The vanilla candidates — the fixed points every operator can run and compare
against — vary nothing: the stock TheOzolith run image for their adapter, no
setup, no knowledge, no policy, the adapter's default model spelled as its
most-pinned provider ID, the model's own default effort.

| Candidate | Adapter | Model |
| --- | --- | --- |
| `vanilla-claude--4e8b75b6/` | claude | claude-sonnet-5 |
| `vanilla-codex--90a33424/` | codex | gpt-5.2-codex |

These are the *current* references, not a closed set. The model IDs are
identity-bearing decisions of record (2026-09-03): a different model, effort,
adapter or base is a different candidate — one more export, one more
directory, nothing to register. Which adapters TheOzolith can materialize is
its verifier's call at ingestion; the bench keeps no list.

Both pin their base image to `ghcr.io/snowfoxbuilds/theozolith-run-<adapter>`
at the-ozolith commit `3c0a5df9609a6c9e1f517bd28a2083d11480c31d` — the merge
that carries the worker revision the bench pins (`19118cae…`; the worker tree
is byte-identical between the two), so the harness inside the image is
exactly the contract the bench consumes.

## Add one

1. Author a config-repo-shaped source (`worker-types/<slug>.toml`, plus
   `knowledge/` / `policy/` trees when the candidate bakes them). Pin the base
   by digest, or let export resolve the tag.
2. Export: `theozolith candidate export --source <src> --type <slug> --out /tmp/<slug>/bundle`
   (`python -m theozolith_control.cli candidate export …` when the console
   script is not on PATH).
3. Name the directory:
   `python -c "from silverquillm.candidate import load_candidate_bundle as l; print(l(__import__('pathlib').Path('/tmp/<slug>/bundle')).hash8)"`
   → `candidates/<slug>--<hash8>/`; move the bundle to `bundle/`, the source
   to `source/`, and write the README (identity triple, candidate hash, what
   the candidate varies, provenance of the base digest).
4. `pytest tests/test_reference_candidates.py -q` — every checked-in candidate
   must ingest, carry its recomputed hash in its name, hold no secret value,
   and re-export byte-identically from its source.
