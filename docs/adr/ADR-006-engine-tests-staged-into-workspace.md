Status: ACCEPTED

Date: 2026-05-23

# ADR-006: Engine Tests Staged Into Workspace

## Context

Agents extending the engine have no local way to verify they have not regressed core mechanics: their only feedback is the Engine Regression score, computed post-run from host-side tests. Without a local regression loop, an agent can make unverified engine assumptions — a non-existent attribute, reuse of an internal flag for a one-shot effect, a manual stack bypass — that a local run would have caught, and only discover the breakage after the run has ended.

Existing policy ([BENCHMARK-RUNNER.md](../specs/BENCHMARK-RUNNER.md) Contamination Controls #1, the "Audited tests are evaluation-only" decision, the [CONTEXT.md](../../CONTEXT.md) relationship line) said audited test suites do not exist in the agent's workspace. This is correct for SOS audited tests (the SOS Card Correctness target — must stay hidden) and FDN audited tests (FDN Card Regression grades reference implementations the agent should not be modifying). It is over-broad for Engine Tests, which exercise generic engine APIs rather than benchmark-target cards.

## Decision

Engine tests live in the workspace at `workspace/engine_tests/` (amended 2026-09-03), visible to the agent. SOS and FDN audited tests remain hidden.

The staged copy is reference-only: these are the Engine Reference Tests, and the agent may edit them, since they may be wrong like the engine (amended 2026-10-02, #126).
Grading reads the hidden Audited Engine Tests at `data/tests/audited/engine/`, seeded from the Engine Reference Tests and maintained independently of them (amended 2026-10-02, #126).
hob-medium and SOS, frozen before that split, grade Engine Regression from the host copy of their staged tests and still forbid editing them.

## Consequences

- **Positive**: Agents gain a local regression-check loop for engine modifications. Closes the silent-engine-regression failure mode. The agent's local validation surface now matches what Engine Regression actually grades.
- **Positive**: SOS and FDN contamination walls remain intact.
- **Negative**: Theoretical training-to-the-test risk for engine tests. Mitigated by the fact that engine tests exercise generic APIs (mana, stack, combat, state-based actions) that any correct engine must implement; "memorizing the test" is largely equivalent to "implementing the engine correctly."
- **Negative**: The staged and graded engine suites drift apart once a graded test is fixed after the Workspace locks (amended 2026-10-02, #126).
- **Neutral**: Workspace layout grows by one directory.
## Alternatives Considered

- **Also stage FDN tests**: Rejected. Agents should not be modifying FDN reference cards; re-running FDN tests during the run would waste budget on non-target cards.
- **Document the engine contract more thoroughly; stage no tests**: Considered. Documentation work (Phase 13 item on `engine_api.md`) is complementary, not a substitute — even a perfect `engine_api.md` cannot tell the agent whether a specific change broke a specific test.
- **Synthetic engine smoke fixtures instead of real tests**: Considered. Adds maintenance overhead and lags behind real engine evolution. The real test suite is the right artifact.
- **Container-level chmod read-only on staged tests**: Rejected. Brittle across runtimes and unnecessary given grading uses host copies.
- **Keep staged tests read-only**: Rejected (amended 2026-10-02, #126). A staged test that encodes an engine defect would block an agent from fixing that defect.

## Amendments

- **2026-09-03**: Updated the staged engine-test path from `workspace/tests/engine/` to `workspace/engine_tests/`, matching the flattened workspace layout adopted in ADR-007 (the workspace is now a pre-built directory copied wholesale rather than assembled by per-file staging). The decision is unchanged — engine tests are agent-visible; SOS and FDN audited tests stay hidden.
- **2026-10-02 (#126)**: Staged engine tests became editable Engine Reference Tests, and grading moved to a hidden Audited Engine Tests copy, so an agent can fix an engine defect a staged test encodes and the graded copy can be fixed after the Workspace locks (ADR-016).

## Relevant PRs

- #126 — Makes staged tests editable Reference Tests and grades hidden Audited Engine Tests under the Known-Best Engine model.
