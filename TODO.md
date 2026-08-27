---

# HOB benchmark generation — current work queue

The MSH benchmark was abandoned at grilling 2026-08-27; its pool-agnostic work
(the V2 engine with the Player Query / Player Decision protocol, the intent-based
`DeterministicPlayer (V2)`, the migrated FDN implementations, and the
replay-validation substrate) carries forward as the three HOB-generation
benchmarks — hob-easy, hob-medium, hob-hard. See `docs/specs/HOB-BENCHMARKS.md`
(SETTLED). The completed MSH task-#1 mission is archived in
`docs/TODO_COMPLETED.md` (Completed 2026-08-27).

**Tracking**: issue #62 stood up the HOB-generation groundwork (the hob-medium
rename, the shared HOB set data at `data/sets/hob.json`, the closing FDN replay
parity report, the run-shape doc sweep, the tests-as-envelope docs, and the
smoke benchmark). The worker-type candidate contract is issue #39.

## Blocked on the operator

- [ ] **(a) HOB card picks** — the operator picks the pools from the pinned HOB
  Draft Set (`data/sets/hob.json`, 321 cards): the hob-medium 5-card *medium*
  pool first, later hob-easy (20 straightforward) and hob-hard (5 difficult).
  Nothing below can start until the picks land.

## Blocked on (a)

- [ ] **(b) Pool, oracles, audited tests, instruction docs** — once cards are picked:
  - Derive each benchmark's pool into `benchmarks/<bench>/data/` from
    `data/sets/hob.json`, and create the `cards/hob/hob_<N>/` target-card tree
    (`card_spec.json` + stub `card_impl.py`) in the workspace.
  - Oracle-first workflow: author the oracle implementation for each HOB card,
    draft audited tests against it (Implementation-Agnostic Testing), then
    human failure-review.
  - Author instruction docs: the benchmark-level tier conventions document plus
    a per-card `instructions.md` (oracle-derived pitfalls; hob-medium = detailed),
    locked with the tier when it enters Benchmarking.
  - `benchmarks/hob-easy/` and `benchmarks/hob-hard/` are created later as hard
    copies of the FDN set + engine (HOB-BENCHMARKS.md).

## Standing constraints

- No scored HOB run happens on the legacy entrypoint lineage; the first scored
  HOB run is the new candidate contract's first consumer (#39). The `--cards` /
  `card_filter` machinery and the `MODE=` env are legacy-lineage-only until they
  are retired in #66.
- `benchmarks/sos/` is frozen — do not touch any file under it.
- The agent envelope for HOB-generation benchmarks is tests-as-envelope: the
  workspace engine is freely modifiable (no additive-only rule, no diff
  policing); the three audited dimensions against the harvested engine are the
  entire judgment (HOB-BENCHMARKS.md, SCORING.md, AUDITED-TEST-SUITE.md).
- Cheap pipeline validation / candidate calibration uses the smoke benchmark
  (`benchmarks/smoke/`), never leaderboard-published.
