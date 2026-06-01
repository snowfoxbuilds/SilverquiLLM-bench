Status: ACCEPTED

Date: 2026-05-23

# ADR-006: Engine Tests Staged Into Workspace

## Context

The 2026-05-23 run exposed a confidence-loop gap: agents extending the engine had no local way to verify they had not regressed core mechanics. Their only feedback was the Engine Regression score, computed post-run from host-side tests. The agent in that run made unverified engine assumptions (a non-existent `cast_zone` attribute, reuse of the `_omniscience_active` flag for a one-shot effect, manual stack bypass in fdn_194) that a local regression run would have caught.

Existing policy ([BENCHMARK-RUNNER.md](http://benchmark-runner.md/) Contamination Controls #1, the "Audited tests are evaluation-only" decision, the [CONTEXT.md](http://context.md/) relationship line) said audited test suites do not exist in the agent's workspace. This is correct for SOS audited tests (the SOS Card Correctness target — must stay hidden) and FDN audited tests (FDN Card Regression grades reference implementations the agent should not be modifying). It is over-broad for Engine Tests, which exercise generic engine APIs rather than benchmark-target cards.

## Decision

Stage `tests/engine/` into the workspace at `workspace/tests/engine/`. SOS and FDN audited tests remain hidden.

Grading uses host-repo copies for all three dimensions; the staged copy is reference-only. The agent prompt forbids modification of staged tests — modifying them produces a false-positive local signal without affecting the score, which is strictly worse than no signal.

## Consequences

- **Positive**: Agents gain a local regression-check loop for engine modifications. Closes the silent-engine-regression failure mode the 2026-05-23 run exhibited. The agent's local validation surface now matches what Engine Regression actually grades.
- **Positive**: SOS and FDN contamination walls remain intact.
- **Negative**: Theoretical training-to-the-test risk for engine tests. Mitigated by the fact that engine tests exercise generic APIs (mana, stack, combat, state-based actions) that any correct engine must implement; "memorizing the test" is largely equivalent to "implementing the engine correctly."
- **Negative**: Adds a new prompt invariant (no test modification) the agent could violate. Mitigated by host-copy grading: modifying staged tests does not change the score.
- **Neutral**: Workspace layout grows by one directory.
## Alternatives Considered

- **Also stage FDN tests**: Rejected. Agents should not be modifying FDN reference cards; re-running FDN tests during the run would waste budget on non-target cards.
- **Document the engine contract more thoroughly; stage no tests**: Considered. Documentation work (Phase 13 item on `engine_api.md`) is complementary, not a substitute — even a perfect `engine_api.md` cannot tell the agent whether a specific change broke a specific test.
- **Synthetic engine smoke fixtures instead of real tests**: Considered. Adds maintenance overhead and lags behind real engine evolution. The real test suite is the right artifact.
- **Container-level chmod read-only on staged tests**: Rejected. Brittle across runtimes and unnecessary given grading uses host copies. Enforce via prompt instead.
