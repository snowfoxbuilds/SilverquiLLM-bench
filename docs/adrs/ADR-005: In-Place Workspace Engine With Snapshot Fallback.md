Status: ACCEPTED

Date: 2026-05-13

# ADR-005: In-Place Workspace Engine With Snapshot Fallback

## Context

The earlier persistent-engine design used a separate `engine_work/` copy inside the agent container. The container architecture has since shifted to treating the staged Workspace as the coherent agent-produced state: agents edit files in place, the runner snapshots the Workspace, and evaluation reads from `workspace_final/`.

The runner also needs recovery from timeout cutoff or scrambled final engine edits without creating artificial combinations of card implementations and engine files that the agent never produced.

## Decision

Agents modify `/workspace/engine/` in place. There is no separate `engine_work/` directory.

The baseline engine remains on the host side, outside the container. The runner diffs the official evaluation Workspace's `engine/` against the host baseline to produce `engine_diff.patch`.

During execution, the runner captures full Workspace snapshots every 60 seconds as host-side Git commits. The `.git` directory is not mounted into the container.

If the final Workspace has unusable engine state, the runner may walk backward through snapshot commits and select the latest whole-Workspace snapshot whose engine passes `tests/engine/`. The selected snapshot is materialized as `docker/<image_dir>/results/<run_name>/workspace_final/` and becomes the official evaluation Workspace.

Snapshot fallback is whole-Workspace fallback. The runner must not combine final card implementations with an earlier engine snapshot.

## Consequences

- **Positive**: The agent works in a simpler, realistic codebase layout with one editable `engine/`.
- **Positive**: `workspace_final/` is a coherent state the agent actually produced.
- **Positive**: Snapshot fallback can recover from timeout-cutoff engine corruption without score-shopping across card implementations.
- **Positive**: Git snapshots provide progress telemetry and historical inspection with deduplicated storage.
- **Negative**: The runner must manage a host-side baseline engine and snapshot repo.
- **Negative**: Fallback selection adds complexity to the evaluation pipeline.
- **Neutral**: If no snapshot passes Engine Regression, the run is marked `no_viable_output_produced`.
## Alternatives Considered

- **Separate ****`engine_work/`**** copy**: Rejected. It adds an artificial distinction inside the Workspace and complicates the mental model for agents.
- **Engine-only rollback**: Rejected. Combining final card implementations with an earlier engine snapshot creates a state the agent never produced.
- **No snapshot fallback**: Rejected. Timeout cutoff can corrupt final files even when a recent coherent Workspace state existed.
- **Use FDN/SOS correctness to select fallback**: Rejected. Fallback selection uses Engine Regression only; using card correctness would become score-shopping.
