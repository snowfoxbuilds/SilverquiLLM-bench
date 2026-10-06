Status: DRAFT

Last updated: 2026-10-06

# Known-Best Engine

How the Known-Best Workspace, Known Defects, and the regression reference scores fit together, so that an agent fixing a real engine defect gains score instead of losing it.

## Context

No benchmark's baseline engine is flawless, and regression suites written against a defective engine punished agents for fixing it (#123).
Benchmarks now ship a baseline that may carry Known Defects, graded by rules-correct Audited Tests that a separate, defect-free Known-Best Engine passes in full.

## Design

### Scope

The design applies to smoke, fra-hard-v2, and every later benchmark (grilling 2026-10-02).
hob-medium, SOS and fra-hard v1 are frozen: they keep their baseline engines, read-only staged tests, and current graded copies, and they take no Known-Best Engine fixes (grilling 2026-10-04).
The Known-Best Engine drives play through Priority Queries and its Workspace predefines a class for every card, face and printed ability; it changes first, and smoke and fra-hard-v2 are ported from it (grilling 2026-10-04).

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
A Platform Test grades a throwaway copy of it through the benchmark grading code and requires every regression Audited Test to pass.
Checks of the engine's internals, and of positions no FDN card reaches through play, are Platform Tests beside it rather than Audited Engine Tests, and a Platform Test requires that no Audited Engine Test writes the turn's lifecycle or calls the engine's stepping (grilling 2026-10-05).

#### Layout

The Known-Best Workspace is the top-level `known_best/` directory, laid out with a benchmark's relative paths so that porting is a plain hard copy with no path rewriting:

```
known_best/
├── workspace/
│   ├── engine/                      Known-Best Engine
│   ├── cards/                       package files and fdn/ (FDN implementations
│   │                                with their FDN Reference Tests)
│   ├── conftest.py
│   ├── pytest.ini
│   ├── test_interface.py            Test Interface (benchmark-owned)
│   ├── test_interface.md            its documentation (benchmark-owned)
│   ├── test_test_interface.py       tests that demonstrate it (not graded)
│   └── test_utils.py                Reference Tests' helpers
└── data/tests/audited/
    ├── fdn/<card_id>/tests.py       FDN Audited Tests
    └── engine/                      Audited Engine Tests
```

| From `known_best/` | To a benchmark |
| --- | --- |
| `workspace/engine/`, `workspace/cards/fdn/` | `workspace/` and the Test Oracle Workspace |
| `workspace/test_interface.py`, `workspace/test_interface.md`, `workspace/test_test_interface.py`, `workspace/test_utils.py` | `workspace/` and the Test Oracle Workspace |
| `data/tests/audited/fdn/`, `data/tests/audited/engine/` | `data/tests/audited/` |
| `data/tests/audited/engine/` | `workspace/engine_tests/`, seeding the Engine Reference Tests |

It deliberately holds no `config.json` (it is not a benchmark), no target-set cards or stubs, no agent-facing documents beyond the Test Interface's own, no Test Oracle Workspace or oracle extension, and no Engine Reference Tests.
Engine Regression grades a benchmark's `data/tests/audited/engine/` whenever that directory exists and otherwise the host copy of `workspace/engine_tests/`, so `known_best/` is graded by exactly the code that grades benchmarks.

### Building a benchmark from it

A benchmark is built by porting a copy of the Known-Best Workspace into it (grilling 2026-10-02):

- **Test Oracle Workspace**: the ported copy plus the benchmark's Test Oracle Impls and any oracle engine extensions. Every benchmark has one; smoke's is the ported copy alone, since its targets are FDN cards it already holds.
- **Audited Tests**: the ported FDN Audited Tests and Audited Engine Tests become the benchmark's `data/tests/audited/fdn/` and `data/tests/audited/engine/`, beside its target-card Audited Tests.
- **Workspace**: the ported engine and FDN implementations plus the benchmark's Known Defects, and Reference Tests (FDN Reference Tests and Engine Reference Tests).

Copies are hard copies, so each benchmark stays self-contained after the Known-Best Workspace moves on.

`scripts/port_from_known_best.py <benchmark>` performs the port and can be re-run whenever the Known-Best Workspace changes; `--check` reports what a port would change, and a Platform Test runs it for every benchmark ported this way.
It owns only the copied paths in the table above, the Test Oracle Workspace's mirrors of the Workspace's `AGENTS.md`, `skills/` and Audited Test suites, and the target cards' Workspace stubs, which it generates from their Card Specs; every other path, such as the agent-facing documents, target Test Oracle Impls and target Audited Tests, is the benchmark's own.
Each Known Defect is recorded as a patch against the Known-Best Workspace, `data/known_defects/<id>.patch`, which the port applies to the Workspace in manifest order; oracle engine extensions may likewise be recorded as patches in `data/oracle_patches/`.
A patch that no longer applies fails the port, and the defect is re-recorded against the new Known-Best code.
A malformed patch, a deletion that would leave content behind, or a path outside the patched tree fails it too, and a failing patch changes nothing; the paths the port owns are synchronized with the Known-Best Workspace, deletions included.
The port builds the whole result in a staged copy and publishes only what differs, so a failure at any step changes nothing; it follows no symlinks — a link anywhere in the benchmark or the Known-Best input fails it before anything is built — checks every path it will replace before replacing any, and replaces whole a path whose type changed, a file that became a directory or the reverse.

### Known Defects

A Known Defect may sit in the baseline engine or in an FDN implementation; agents may fix either, and FDN Card Regression rewards an FDN fix the way Engine Regression rewards an engine fix (grilling 2026-10-02).
Each benchmark lists its Known Defects in a host-only `data/known_defects.json` (grilling 2026-10-02).
An entry names the defect, its rule citation, whether it is `inherited` or `seeded`, and the Audited Tests it makes fail.
Reference scores pool the FDN and engine Audited Tests into one Combined Regression, so an entry needs no component and its failing tests may sit in either suite (grilling 2026-10-02).
Seeded Defects are fixed per benchmark version: they are part of the Workspace and freeze with it, so every run on that version sees the same engine.

Nothing constrains what the Reference Tests say about a Known Defect: they may reveal it, miss it, or encode it, because tests are not instructions.
The Workspace's conventions document says the engine may have deficiencies and bugs, and so may the existing tests; it says nothing more about either.

CI checks, for every benchmark in scope:

1. The Test Oracle Workspace passes every Audited Test of all three dimensions.
2. The unmodified Workspace fails exactly the Audited Tests the manifest lists, and passes the rest of the regression suites.

Both checks are Platform Tests, one call per dimension so each stays within the test timeout: `tests/known_defect_checks.py` provides `oracle_problems` and `workspace_problems`, which return the problems found and `[]` when the check passes.

#### Manifest

```json
{
  "schema_version": 1,
  "benchmark": "fra-hard",
  "defects": [
    {
      "id": "zone-change-keeps-status",
      "description": "A permanent that changes zones stays the same object and keeps its counters, tapped status and marked damage.",
      "rules": ["CR 400.7", "CR 603.10a"],
      "kind": "inherited",
      "failing_tests": {
        "engine_regression": ["zone_change/test_lki.py::test_counters_reset"],
        "fdn_regression": ["fdn_66/tests.py::test_dies_returns_with_one_fewer_revival"]
      }
    }
  ]
}
```

- The file is a regular UTF-8 JSON file of at most 1 MiB with no duplicate keys, and every object has exactly the keys shown.
- `benchmark` is the benchmark's directory name; a benchmark with no Known Defects ships `"defects": []`.
- `id` is unique, lowercase letters, digits and hyphens, at most 64 characters; `description` is non-empty; `rules` is a non-empty list of distinct citations like `CR 400.7` or `CR 603.10a`; `kind` is `inherited` or `seeded`.
- `failing_tests` maps `fdn_regression`, `engine_regression` or both to a non-empty list of distinct Audited Test ids. The same test may be listed under two defects; the unmodified Workspace is expected to fail their union.

An Audited Test id is the pytest node id relative to its suite's graded root:

| Suite | Id | Example |
| --- | --- | --- |
| Audited Engine Tests | the node id under `data/tests/audited/engine/` | `zone_change/test_lki.py::test_counters_reset` |
| FDN Audited Tests | `<card_id>/` plus the card suite's node id | `fdn_126/tests.py::TestZimoneDoubleAbility::test_leave_and_return_target_rejected` |

The baseline reference grade and Combined Regression name tests the same way.

### Baseline reference grade

The Baseline Score is produced, never hand-written: the grader grades the unmodified Workspace once per grading-inputs digest and Workspace content, and that baseline reference grade records the per-test outcomes (grilling 2026-10-02).
The grading-inputs digest alone does not cover the Workspace's engine or FDN implementations, so a defect fixed in a Beta Workspace must still produce a new baseline reference grade.
A benchmark reports reference scores only once it has a Known Defect manifest; hob-medium and SOS have none.
Every run graded under the same digest reports against it (see [SCORING.md](SCORING.md) → Regression reference scores).

The grade's key also covers the grading-code digest and the grader image, since either can change an outcome, so it is the benchmark identity plus those four: grading inputs, grading code, Workspace content and grader image.
The grade is computed on demand, by the first run, recovery or regrade that needs it, through that caller's own grader, and cached host-side at `<state_root>/baseline-grades/<benchmark>/<sha256 of the key>.json`.
It records each regression dimension's raw pass/total, missing reasons and per-test outcomes.
Only a complete grade is cached: failing Audited Tests are what it records, and the FDN coverage gap every run shares does not count against it, but a grading that raised, timed out, failed to collect a suite or executed none is reported for that attempt only and graded again by the next request; a damaged, mismatched or incomplete cached file is graded again too.
The grading inputs are checked against the requested digest before and after the grading, and a grade whose inputs changed meanwhile is reported as `grading_inputs_changed_during_grading` and never cached, so a cached grade always belongs to the digest it is filed under.

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
| [ADR-017](../adr/ADR-017-priority-actions-are-player-queries.md) | Priority actions are Player Queries chosen through the players' answers |
| [ADR-018](../adr/ADR-018-audited-tests-play-as-two-players-at-a-table.md) | Audited Tests build a position, play it and judge it only as players at the table would |
