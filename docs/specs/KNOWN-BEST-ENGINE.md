Status: DRAFT

Last updated: 2026-10-02

# Known-Best Engine

How the Known-Best Workspace, Known Defects, and the regression reference scores fit together, so that an agent fixing a real engine defect gains score instead of losing it.

## Context

No benchmark's baseline engine is flawless, and regression suites written against a defective engine punished agents for fixing it (#123).
Benchmarks now ship a baseline that may carry Known Defects, graded by rules-correct Audited Tests that a separate, defect-free Known-Best Engine passes in full.

## Design

### Scope

The design applies to smoke, fra-hard, and every later benchmark (grilling 2026-10-02).
hob-medium and SOS are frozen: they keep their baseline engines, read-only staged tests, and current graded copies, and they take no Known-Best Engine fixes.

### Known-Best Workspace

The Known-Best Workspace lives at the repo top level, separate from every `benchmarks/<benchmark>/` directory (grilling 2026-10-02).
It holds:

| Content | Role |
| --- | --- |
| Known-Best Engine | The engine with every Known Defect fixed |
| FDN implementations | The card implementations the FDN regression suite runs against, with every Known Defect fixed |
| FDN Audited Tests | The full FDN Card Regression suite |
| Audited Engine Tests | The full Engine Regression suite |

It is seeded from hob-medium's Workspace without any oracle extensions, then has the already-identified Known Defects fixed: the zone-change reset that preserves last-known information (CR 400.7, 110.5, 111.7, 603.10a) and the engine or FDN-implementation defects behind the eight FDN cases hob-medium cut from its graded suite as baseline gaps.
Those eight cases and dedicated zone-change Audited Engine Tests join its suites; seeding is complete when every regression Audited Test passes on it.

### Building a benchmark from it

A benchmark is built by porting a copy of the Known-Best Workspace into it (grilling 2026-10-02):

- **Test Oracle Workspace**: the ported copy plus the benchmark's Test Oracle Impls and any oracle engine extensions. Every benchmark has one; smoke's is the ported copy alone, since its targets are FDN cards it already holds.
- **Audited Tests**: the ported FDN Audited Tests and Audited Engine Tests become the benchmark's `data/tests/audited/fdn/` and `data/tests/audited/engine/`, beside its target-card Audited Tests.
- **Workspace**: the ported engine and FDN implementations plus the benchmark's Known Defects, and Reference Tests (FDN Reference Tests and Engine Reference Tests).

Copies are hard copies, so each benchmark stays self-contained after the Known-Best Workspace moves on.

### Known Defects

A Known Defect may sit in the baseline engine or in an FDN implementation; agents may fix either, and FDN Card Regression rewards an FDN fix the way Engine Regression rewards an engine fix (grilling 2026-10-02).
Each benchmark lists its Known Defects in a host-only `data/known_defects.json` (grilling 2026-10-02).
An entry names the defect, its rule citation, its component (`engine` or `fdn`), whether it is `inherited` or `seeded`, and the Audited Tests it makes fail.
Engine and FDN Known Defects are scored separately: each counts toward its own regression dimension's Baseline Score and fixed count (grilling 2026-10-02).
Seeded Defects are fixed per benchmark version: they are part of the Workspace and freeze with it, so every run on that version sees the same engine.

Nothing constrains what the Reference Tests say about a Known Defect: they may reveal it, miss it, or encode it, because tests are not instructions.
The Workspace's conventions document says the engine may have deficiencies and bugs, and so may the existing tests; it says nothing more about either.

CI checks, for every benchmark in scope:

1. The Test Oracle Workspace passes every Audited Test of all three dimensions.
2. The unmodified Workspace fails exactly the Audited Tests the manifest lists, and passes the rest of the regression suites.

### Baseline reference grade

The Baseline Score is produced, never hand-written: the grader grades the unmodified Workspace once per grading-inputs digest, and that baseline reference grade records the per-test outcomes (grilling 2026-10-02).
Every run graded under the same digest reports against it (see [SCORING.md](SCORING.md) → Regression reference scores).

### Fixing a newly found defect

When review of a run turns up a new defect (grilling 2026-10-02):

1. Fix it in the Known-Best Workspace's engine or FDN implementation and add any Audited Test that pins it.
2. Port the fix into the Test Oracle Workspace of every non-Released benchmark that carries the defect.
3. Add an `inherited` entry to each such benchmark's manifest and update its Audited Tests.
4. Recompute the baseline reference grade and regrade every run of those benchmarks.

Porting the fix into a benchmark's Workspace as well is optional in Beta and impossible from Benchmarking on; a defect fixed in the Workspace leaves the manifest.
Released benchmarks never take the fix.

### Wrong Audited Tests

A regression Audited Test found to be wrong is fixed in the benchmark's graded copy while the benchmark is in Beta or Benchmarking, then the baseline reference grade is recomputed and every run regraded (grilling 2026-10-02).
The Workspace's Reference Test copy stays as it is once the Workspace locks.
There is no per-run dispute or pending state; agents' edits to Reference Tests, visible in each Workspace Archive diff, are evidence for that review and never grading input.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-006](../adr/ADR-006-engine-tests-staged-into-workspace.md) | Engine Reference Tests are staged and editable; grading reads hidden Audited Engine Tests |
| [ADR-010](../adr/ADR-010-test-oracle-workspace-uses-independent-engine.md) | Oracle engines are independent and start from the ported Known-Best Engine |
| [ADR-011](../adr/ADR-011-three-tier-benchmark-locking.md) | Three-Tier Benchmark Locking |
| [ADR-016](../adr/ADR-016-baseline-engines-may-carry-known-defects.md) | Baseline engines may carry Known Defects, scored against a separate Known-Best Engine |
