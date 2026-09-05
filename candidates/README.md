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
binds from its own environment (`ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`
for claude, `CODEX_AUTH_JSON` for codex — the slot names TheOzolith's adapters
register, `theozolith_worker.config._ADAPTER_CREDENTIAL_ENV`, …).

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

Promote it from your Config Repo (`docs/specs/BENCHMARK-CANDIDATES.md`):

```bash
python scripts/promote_candidate.py <config-repo> <worker-type> [--slug NAME] [--docker-config DIR] [--dry-run]
```

The script exports the bundle with TheOzolith's tooling, ingests it through
the bench's own path (identity recomputed, secret values refused), writes
`candidates/<slug>--<hash8>/` with the definition (base pinned by digest), the
referenced knowledge and policy source trees, the bundle, and a README stub —
proving first that re-exporting the vendored source reproduces the bundle
byte for byte. **Vendor-at-promote is strict**: a knowledge tree the
definition references must exist in the Config Repo and carry a regular file
named `PUBLISHABLE` at its root (your explicit declaration; the marker never
enters the compiled tree or the identity). Without it the candidate cannot be
promoted and its results cannot be published.

**The whole directory is public.** Before the final rename the complete staged
tree — bundle, vendored definition, knowledge and policy source (the
`PUBLISHABLE` marker included), README — is scanned with the bench's
credential detector (API keys, GitHub / AWS / Slack tokens, private-key
blocks, JWTs, bearer credentials, a declared secret slot assigned a value); a
hit refuses naming the file and the shape, never the value. Slot assignment
detection has no length or character-set rule: `SLOT=x`, `SLOT = "short"`,
`SLOT: opaque/+value==`, `"SLOT": "…"` and `'SLOT' = 'value with spaces'` are
all values — a placeholder such as `<your key>` too, since nothing
distinguishes it from a secret by shape — while an empty assignment (`SLOT =
""`, the way the definition's `[secrets]` table declares a slot), a
declaration list and prose that merely names the slot are not. A quoted value
is taken whole to its closing quote, escaped quotes and backslashes included,
so a JSON value that contains a quote is one value, never two fragments. Write
docs as prose, not as an example assignment. The generated README and
definition name no host-local path (the source is "the operator's Config
Repo"; a `TODO(promote)` lets you add a safe repository label and revision).

**Dedup is by identity and source.** The same identity already promoted
under the same name is a no-op only when the existing copy is whole and
equivalent — its bundle verifies, its `source/` re-exports to its bundle byte
for byte, and its `source/` equals what you are promoting byte for byte. Your
completed README is never compared. A tampered, missing or differing vendored
source, a bundle that does not recompute to its name, or the same identity
under another slug is a refusal that leaves the existing directory untouched.
The script never runs git.

**A refusal or a dry run leaves the tree exactly as it was.** The slug is
checked before anything is staged; staging lives beside the candidates
(`candidates/.promote-<slug>-<nonce>/`, same filesystem, so the final rename
is atomic) and is removed strictly — never with errors ignored — because it
may hold the very content promotion refused, a rejected credential value
included; a `candidates/` directory the invocation created is removed again
when it is left empty — only if the path still names the very directory the
script created and that directory is empty, so a replacement or anything
someone else wrote there meanwhile is never removed. If staging *cannot* be
removed, or that directory cannot be removed, is no longer the one the script
made or is no longer empty, the script does not pretend: it prints the
refusal, then `CLEANUP FAILED: …` naming what is kept (`<path> is KEPT` for
staging), and exits 2. Inspect a retained staging directory and remove it by
hand (`rm -rf`); it is gitignored (`candidates/.promote-*`) so it can never
be committed by accident, and its bytes are never echoed.

Then:

1. Complete the README — every `TODO(promote)` (what the candidate varies,
   where the base digest came from). The platform test refuses a checked-in
   README that still carries the placeholder.
2. `pytest tests/test_reference_candidates.py -q` — every checked-in candidate
   must be a real directory in the tree (a symlink under a candidate name is
   rejected, never followed: a curated candidate is what the repository
   holds, not what a link on one host points at), ingest, carry its
   recomputed hash in its name, hold no secret value anywhere in its
   directory (the same scanner promotion uses), re-export byte-identically
   from its source, and vendor a `PUBLISHABLE` knowledge tree when it bakes
   one. The publish gate holds the same line: a run traces only to a real
   `candidates/<slug>--<hash8>/` with a real `bundle/`.
3. Review the diff and commit — the commit is the approval stamp.

A bundle exported by hand (`theozolith candidate export --source <src>
--type <slug> --out <dir>`) can be run directly with
`silverquillm run --candidate <dir>`; only a promoted candidate can have its
results published.
