Status: ACCEPTED

Date: 2026-05-13

# ADR-004: Docker Agent Containers Replace Python Adapters

## Context

The original benchmark harness used Python agent adapters, per-card workspaces, strategy classes, harness-managed blind/test-informed rounds, and application-level contamination checks. That design created structural isolation problems: agents could be configured with the wrong repository root, tool caches produced false contamination violations, output streaming and timeout handling were fragile, and the per-card prompt model did not test long-running coding-agent behavior. The project now needs the v1 benchmark architecture to be contamination-resistant, agent-agnostic, and realistic for multi-hour implementation tasks.

## Decision

Use isolated Docker containers as the execution boundary for Benchmark Candidates (amended 2026-09-26).

A Karn Benchmark Candidate pairs an immutable Docker image with the Construct Definition selecting its runtime behavior (amended 2026-09-26).
The benchmark supplies its own task and instruction data, without a separate basic/planned mode selector.
The host does not orchestrate the agent's reasoning or iteration: it stages a Workspace, supplies the declared runtime facilities, launches the candidate, harvests outputs and observations, and evaluates the implementation.

The file-based contract is:

- Input Workspace supplied through the definition's declared workspace mount
- Output files supplied and collected through the declared file interface
- Authentication supplied through the selected runtime facilities, including Karn login lifecycle hooks (amended 2026-09-26)
- Implementations and agent-written tests harvested from the benchmark's target card directories
- Agent engine modifications harvested from `/workspace/engine/`, which the agent edits in place — there is no separate `engine_work/` (amended 2026-09-03)
- Declared output artifacts, container logs, and available native telemetry retained as observations
Python adapters, per-card workspaces, strategy classes, harness-managed rounds, and application-level contamination checking are legacy implementation details to remove or migrate away from. Agent-internal iteration belongs inside the container entrypoint or the agent itself, not the host runner.

## Consequences

- **Positive**: Isolation is structural. Audited tests, harness source, prior results, and reference SOS implementations are not mounted into the container.
- **Positive**: The runner becomes simpler and more reliable: stage, launch, harvest, evaluate.
- **Positive**: New agents enter through Karn images and definitions without host-side Python classes orchestrating their behavior.
- **Positive**: Full-set, long-running workloads test planning, self-pacing, knowledge accumulation, and long-context endurance.
- **Positive**: Task guidance is explicit benchmark data and candidate behavior remains independently identifiable.
- **Negative**: The runner has less fine-grained insight into what the agent is doing mid-run.
- **Negative**: Per-card timeout and rollback semantics are weaker; partial results are harvested after whole-container timeout.
- **Negative**: Debugging agent behavior depends on progress logs, stdout, stderr, and harvested files rather than adapter-level structured callbacks.
- **Neutral**: Karn candidate identity binds the immutable image and selected definition; an image name alone is not that identity (amended 2026-09-26).
- **Neutral**: Agent tests remain artifacts in v1. Scoring uses audited tests only.
## Alternatives Considered

- **Keep Python adapters**: Rejected because adapter configuration, subprocess lifecycle, streaming, and contamination checking were fragile and agent-specific.
- **Per-card workspaces**: Rejected because the workload is artificial and prevents agents from demonstrating long-running planning and reusable engine-extension behavior.
- **Host-orchestrated strategy classes**: Rejected because the host runner should not encode agent iteration behavior. Agent strategy belongs in the image/entrypoint.
- **Application-level contamination checker**: Rejected as the primary isolation mechanism. It remains useful as a diagnostic during migration, but structural container isolation is the v1 guarantee.

## Amendments

- **2026-09-03**: Clarified that the agent's engine modifications are harvested from `/workspace/engine/`, edited in place — there is no separate `engine_work/` directory (aligns with ADR-005).
- **2026-09-26**: Applied the Karn image/definition boundary and selected authentication facilities, with benchmark-owned instruction data. Container isolation and implementation harvesting remain; [ADR-0012](ADR-0012-independent-host-for-karn-benchmark-candidates.md) records the independent v4 host decision.
