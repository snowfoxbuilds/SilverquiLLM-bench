Status: ACCEPTED

Date: 2026-05-13

# ADR-004: Docker Agent Containers Replace Python Adapters

## Context

The original benchmark harness used Python agent adapters, per-card workspaces, strategy classes, harness-managed blind/test-informed rounds, and application-level contamination checks. That design created structural isolation problems: agents could be configured with the wrong repository root, tool caches produced false contamination violations, output streaming and timeout handling were fragile, and the per-card prompt model did not test long-running coding-agent behavior. The project now needs the v1 benchmark architecture to be contamination-resistant, agent-agnostic, and realistic for multi-hour implementation tasks.

## Decision

Use Docker-based Agent Containers as the canonical v1 benchmark architecture.

Each Docker image is the full agent configuration: agent CLI, benchmark mode, strategy variant, model selection, and prompt behavior. The host runner does not know agent internals. The runner only stages a Workspace, launches the selected image, waits for the container to exit, harvests file-based outputs, and runs post-run evaluation.

The file-based contract is:

- Input Workspace mounted at `/workspace/`
- Output directory mounted at `/output/`
- API credentials passed as environment variables
- Agent implementations harvested from `/workspace/cards/sos/*/card_impl.py`
- Agent tests harvested from `/workspace/cards/sos/*/tests.py`
- Agent engine modifications harvested from `/workspace/engine/` (amended 2026-09-03, ADR-005 — engine is edited in place; there is no separate `engine_work/`)
- Progress and logs harvested from `/output/`
Python adapters, per-card workspaces, strategy classes, harness-managed rounds, and application-level contamination checking are legacy implementation details to remove or migrate away from. Agent-internal iteration belongs inside the container entrypoint or the agent itself, not the host runner.

## Consequences

- **Positive**: Isolation is structural. Audited tests, harness source, prior results, and reference SOS implementations are not mounted into the container.
- **Positive**: The runner becomes simpler and more reliable: stage, launch, harvest, evaluate.
- **Positive**: New agents can be added by building new Docker images rather than writing Python adapter classes.
- **Positive**: Full-set, long-running workloads test planning, self-pacing, knowledge accumulation, and long-context endurance.
- **Positive**: Agent mode comparisons are clean: Blind Mode and Tested Mode are separate images and separate runs.
- **Negative**: The runner has less fine-grained insight into what the agent is doing mid-run.
- **Negative**: Per-card timeout and rollback semantics are weaker; partial results are harvested after whole-container timeout.
- **Negative**: Debugging agent behavior depends on progress logs, stdout, stderr, and harvested files rather than adapter-level structured callbacks.
- **Neutral**: Docker image naming becomes part of the benchmark identity, for example `silverquillm-pi-blind:latest`.
- **Neutral**: Agent tests remain artifacts in v1. Scoring uses audited tests only.
## Alternatives Considered

- **Keep Python adapters**: Rejected because adapter configuration, subprocess lifecycle, streaming, and contamination checking were fragile and agent-specific.
- **Per-card workspaces**: Rejected because the workload is artificial and prevents agents from demonstrating long-running planning and reusable engine-extension behavior.
- **Host-orchestrated strategy classes**: Rejected because the host runner should not encode agent iteration behavior. Agent strategy belongs in the image/entrypoint.
- **Application-level contamination checker**: Rejected as the primary isolation mechanism. It remains useful as a diagnostic during migration, but structural container isolation is the v1 guarantee.
