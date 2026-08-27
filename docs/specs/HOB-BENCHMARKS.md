Status: DRAFT (created at grilling 2026-08-27; all decisions below settled that session)

# HOB Benchmarks

The three HOB-generation benchmarks — hob-easy, hob-medium, hob-hard — succeeding the abandoned MSH benchmark (see MSH-BENCHMARK.md, ABANDONED).

## Context

MSH aged out as a contamination-fresh pool before any benchmark ran on it. Its pool-agnostic work — the V2 engine with the Player Query / Player Decision protocol ([DECISION-MODEL.md](DECISION-MODEL.md)), the intent-based DeterministicPlayer (V2), the migrated FDN implementations, and the replay-validation substrate (closed clean; see PROJECT-OVERVIEW.md Phase 3) — carries forward wholesale.

**Card pool source**: Magic: The Gathering | The Hobbit, main expansion set code HOB, 321 cards, released 2026-08-14. Mechanics: Adventure (primary returning), Storied, Recruit, hone counters, Amass.

## The three benchmarks

One benchmark = one problem set. Each tier is a **separate benchmark** with its own `config.json`, card pool, audited-test tree, and ADR-011 lock tier — never workloads or modes of a shared benchmark. The operator picks all cards. Work starts with hob-medium.

| Benchmark | Cards | Agent-visible instructions | Tests | Engine-change requirement |
| --- | --- | --- | --- | --- |
| `hob-easy` | 20 straightforward | Clear instructions + pitfalls | Pure implementation + large-context handling | Little/none |
| `hob-medium` | 5 medium | Detailed instructions + pitfalls | Regular implementation task | Some |
| `hob-hard` | 5 difficult | None (card spec only) | Reasoning / exploration | Extensive |

Required-engine-change depth is the difficulty knob. Tiers differ only in *what the agent is given*, never in how they are scored.

## Run shape

- A Benchmark Run is one container session consuming the benchmark's **entire** problem set in a single Workspace. There is no card-subset ("workload") notion — that term is retired (CONTEXT.md).
- Cheap pipeline validation / candidate calibration uses a dedicated **smoke benchmark**: its own small problem set of already-validated FDN cards (known-good oracles and audited tests), never leaderboard-published, run like any other benchmark.
- Checkpoints are retired (MSH-CHECKPOINTS.md, RETIRED). ADR-008/009 resume legs cover crash recovery.
- Runs happen under the worker-type candidate contract (issue #39): run spec = candidate + mode + benchmark + budget. **No scored HOB run happens on the legacy entrypoint lineage** — the first scored HOB run is the new contract's first consumer.

## Repo layout

- No `benchmarks/hob/` umbrella. `benchmarks/msh/` is `git mv`-renamed to `benchmarks/hob-medium/`, persisting the FDN/engine git history; MSH pool artifacts (`data/msh.json`, MSH card stubs, `fetch_data.py` MSH targeting) are deleted in the move.
- `hob-easy/` and `hob-hard/` are created later as **hard copies** of the FDN set + engine (the SOS↔MSH decoupling rule applies between sibling benchmarks too; drift between tiers is accepted by design).
- Full HOB set data is fetched once to the shared `data/sets/hob.json` (raw Scryfall material, benchmark-neutral). Each benchmark's `data/` holds only its own pool, derived from it.

## Engine rules

- **Freeze**: the agent-visible workspace engine locks when a tier enters Benchmarking (ADR-011 machinery). Within a lock tier, every candidate sees the identical engine — this is what makes "requires some engine changes" a stable property of the benchmark. Oracle iteration touches HOB card implementations, audited tests, and instruction docs only — never the FDN implementations or the staged workspace engine.
- **Agent envelope**: agents may modify the workspace engine freely — no additive-only rule, no diff policing. The three audited dimensions are the entire judgment, all run against the harvested engine: HOB card correctness, FDN card regression, engine regression. Audited tests judge card behavior by simulating gameplay (implementation-agnostic testing); this mechanism is already implemented.

## Instruction documents

- Two granularities per tier: a benchmark-level conventions document (engine conventions, what a good implementation looks like, the envelope rule above) and a per-card `instructions.md` beside `card_spec.json`, staged into the workspace card directory.
- Pitfalls are **discovered, not invented**: authored from what the oracle implementation actually surfaced (oracle-first workflow; the oracle iterates while benchmarks run).
- Instruction docs shape difficulty as much as the pool does: they are locked benchmark data, frozen with the tier at Benchmarking; changing them afterward is a benchmark-version event.
- Per tier: hob-easy clear, hob-medium detailed, hob-hard none.

## Evaluation

Oracle-first audited tests are the sole scored method for all three tiers (Audited Eval, unchanged pipeline): oracle implementation → audited tests drafted against it → human failure-review → agent runs scored on the three dimensions.

## Decisions

- **FDN replay validation closed**; residue 100% attributed, no further burn-down phases. [SETTLED — Grilling 2026-08-27]
- **MSH abandoned as a benchmark; pool-agnostic work kept.** [SETTLED — Grilling 2026-08-27]
- **Tiers are separate benchmarks**, not workloads/modes. [SETTLED — Grilling 2026-08-27]
- **"Workload" retired**; run spec = candidate + mode + benchmark + budget; smoke via dedicated smoke benchmark. [SETTLED — Grilling 2026-08-27]
- **Layout**: `msh` → `hob-medium` rename preserving history; easy/hard as later hard copies; shared raw set data in `data/sets/hob.json`. [SETTLED — Grilling 2026-08-27]
- **Engine freeze at Benchmarking; oracle iterates on HOB impls/tests only.** [SETTLED — Grilling 2026-08-27]
- **Tests-as-envelope**: engine freely modifiable; the three audited dimensions are the whole judgment. [SETTLED — Grilling 2026-08-27]
- **Checkpoints retired.** [SETTLED — Grilling 2026-08-27]
- **Instruction docs**: tier conventions doc + per-card `instructions.md`, oracle-derived, locked with the tier. [SETTLED — Grilling 2026-08-27]
- **Engine-change depth is the difficulty knob** (easy little/none, medium some, hard extensive). [SETTLED — Grilling 2026-08-27]
- **Candidate contract**: candidates enter as self-contained Candidate Bundles (adapter-agnostic; claude + codex today, Pi later); identity independently recomputed; bench driver imitates the substrate job-dir contract at full fidelity (synthetic-issue task file, `input/` tree, `output/proposal.json` applied post-exit). [SETTLED — Grilling 2026-08-27]
