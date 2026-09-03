Status: ACCEPTED

Date: 2026-05-24

# ADR-007: Workspace As Pre-Built Directory

## Context

Earlier staging logic assembled the Workspace per-run by copying files from multiple source locations: engine source from `engine/`, cards from `cards/`, separate reference docs (`engine_api.md`, `base_classes.py`, `test_utils.md`), and writing per-run files. Each new agent-visible artifact required a code change in `stage_workspace()` and a corresponding spec update, creating drift between the staging code and the Workspace contract spec.

This pattern is fragile: spec docs reference reference docs that have already been archived; new artifacts (`AGENTS.md`, `PROJECT_MAP.md`, test scaffolding, `tests/cards/fdn/`, `.gitignore`) need staging steps that may not yet be implemented; and the assembled Workspace never exists as a single browseable directory anyone can inspect or test against in dev.

## Decision

The Workspace source-of-truth is a real directory in the bench repo at `benchmarks/sos/workspace/`. Staging consists of four steps:

1. Recursively copy `benchmarks/sos/workspace/` from the bench repo into a per-run tmp directory.
2. Write `prompt.md` (User Prompt) and `run_manifest.json` (`timeout_seconds` + `deadline_utc`) into the copy. The manifest write happens immediately before container launch.
3. Run `git init && git add -A && git commit -m "initial workspace"` inside the copy so the agent has clean version-control state and Output Snapshots have a base commit.
4. Mount the copy at `/workspace/` when launching the agent container.
The canonical engine lives at `benchmarks/sos/workspace/engine/` as a single source. Bench tooling imports from there (`from benchmarks.sos.workspace.engine import ...`), so agent-engine and eval-engine are identical by construction.

Workspace tests must be runnable locally from the workspace directory in dev: `cd benchmarks/sos/workspace && pytest cards/fdn/ && pytest tests/engine/` must pass as a meta-check that the workspace itself is valid before staging.

ADRs are not staged into the Workspace. They live host-side under the Notion ADRs container and sync to the SilverquiLLM repo as needed; the agent never sees them.

## Consequences

- **Positive**: Workspace contents are inspectable, dev-testable, and version-controlled in the bench repo without running the harness.
- **Positive**: Staging code collapses from N per-file copies to one `cp -r` + per-run writes + `git init`. No drift between staging logic and the spec contract.
- **Positive**: Evaluation and agent share the engine by construction (single Python import path), eliminating engine-version mismatch as a class of bugs.
- **Positive**: Spec docs ([WORKSPACE-CONTRACT.md](../specs/WORKSPACE-CONTRACT.md)) collapse to "see the directory" — no need to enumerate file lists in two places.
- **Negative**: The bench's Python package layout becomes unusual: the canonical engine lives under `benchmarks/sos/workspace/engine/` rather than top-level `engine/`. Bench tooling imports via the longer path.
- **Negative**: Reversing this decision means rewriting `stage_workspace()` for per-file assembly again — half-day of work, not weeks, but non-trivial.
- **Neutral**: SOS Card Stubs (`class CardName(CardImpl): pass`) live in the workspace as version-controlled files; the agent's task is to extend them. This is consistent with how FDN reference implementations live in the same Workspace directory.
## Alternatives Considered

- **Per-file staging (status quo before this ADR)**: Rejected. Every new agent-visible artifact requires a staging code change and creates spec/code drift. The drift between [BENCHMARK-RUNNER.md](../specs/BENCHMARK-RUNNER.md) and the actual `stage_workspace()` is a concrete example.
- **Top-level engine with build-time copy to workspace**: Rejected. Two copies create drift between eval-engine and agent-engine; subtle bugs become possible where they diverge.
- **Symlink ****`workspace/engine`**** → top-level ****`engine`**: Rejected. Breaks under `cp -r` without `-L`, and breaks on Windows dev environments.
- **`NotImplementedError`**** SOS card stubs**: Rejected — too strict. Failing tests get in the way of harness flexibility (e.g., the harness wanting to do things in a different order). SOS Card Stubs use `pass` bodies, relying on `CardImpl`'s no-op-by-default hooks for runnable starting state.
