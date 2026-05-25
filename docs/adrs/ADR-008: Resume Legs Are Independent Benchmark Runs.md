Status: ACCEPTED

Date: 2026-05-25

# ADR-008: Resume Legs Are Independent Benchmark Runs

## Context

Long benchmark runs (multi-hour, sometimes 4–8 hours) occasionally exit before producing useful final results. Common causes: agent process death, container hang, host process kill, snapshot fallback rolling back 15+ minutes of work the agent had actually completed but couldn't snapshot in a viable engine state, or the operator pressing Ctrl-C to recover from an observable stall.

Operators want a way to recover the lost time without re-staging from scratch — the agent has produced real partial work (card implementations, engine changes, agent-internal tracking decisions) that shouldn't be thrown away just because the harness deadline passed.

The intuitive design is "extend the prior run": append another timeout's worth of wall-clock to the existing run, keep writing to the same results directory, treat it as one continuous Benchmark Run. This intuition is wrong, and the rest of the resume design depends on rejecting it.

## Decision

Resume is implemented as a fresh Benchmark Run that stages from the prior run's `workspace_final/` instead of `benchmarks/sos/workspace/`. Each Resume Leg has its own `run_name`, results directory, Hard Timeout, snapshots, evaluation, and `run_summary.json`. Legs are linked via the `resumed_from` field. The sequence of linked Runs is a Resume Chain.

CLI:

```bash
silverquillm resume <prior-run-id> [--timeout ...] [--image ...] [--card-filter ...]
```

Staging variant: copy prior `workspace_final/` wholesale, overwrite only `prompt.md` and `run_manifest.json`, skip `git init` (prior `.git` history is preserved). See [WORKSPACE-CONTRACT.md](http://workspace-contract.md/) → Resume staging variant.

Image: `--image` defaults to the prior run's `docker_image`; explicit override allowed and recorded as `resumed_image_changed: true` in the new leg's `run_summary.json`.

Prompt augmentation: the runner appends a Resume Preamble to the User Prompt informing the agent that this is a resume of `<prior-run-id>` and that prior tests/implementations may already exist. Conditional additional lines disclose (a) snapshot fallback rollback when the prior run used it, and (b) image change when `--image` differs from the prior run's image. The preamble is image-agnostic — agents with no internal coordinator/cycle structure benefit equally.

Refuse conditions: prior `run_status == no_viable_output_produced`, or `workspace_final/` missing. A `--from-snapshots` opt-in flag for borderline cases is a future addition.

Leaderboard validity for Resume Legs is deferred. The existing `leaderboard_valid` field in `run_summary.json` is the eventual control surface; default for legs is unspecified until leaderboard policy is formalized.

The Workspace Contract is unchanged. Tracking files like `KEY_DECISIONS.md`, `FILES_MODIFIED.json`, `RUN_DECISIONS.md`, and `MODEL_AUDIT.jsonl` remain agent-prompt-layer conventions, not part of the contract. Resume detection and continuation logic that depends on them lives in the prompt layer (e.g., the Pi-blind coordinator prompt template), not in the runner.

## Consequences

- **Positive — clean audit trail**: Each leg's results are independently inspectable and evaluatable. `docker/<image-dir>/results/<run_name>/` is always one self-contained run, never a partial palimpsest of multiple resume attempts.
- **Positive — snapshot integrity**: Each leg has its own snapshot stream. The prior run's snapshots aren't perturbed by the resume leg's continuation. Snapshot fallback semantics are unchanged per leg.
- **Positive — leaderboard flexibility**: Per-leg `leaderboard_valid` lets us formalize policy later without retroactive surgery. Equally compatible with "all legs disqualified," "first leg only counts," or wall-clock-stratified scoring.
- **Positive — cross-agent resume**: Mechanically supported via `--image` override. Cross-image legs naturally land under the new image's results directory, since results dir is derived from `--image`.
- **Positive — prompt-layer freedom**: Specs say nothing about how the agent uses the inherited Workspace. Coordinator-style prompts can detect resume via git log + custom tracking files; other prompts can ignore the resume and re-do work. Both are valid.
- **Negative — chain traversal required**: To see "the whole story" of a resumed run, you walk the chain via `resumed_from`. A future `silverquillm chain <run-id>` reporter is a natural follow-up.
- **Negative — disk usage**: A resumed run roughly doubles disk usage (the prior `workspace_final/` is wholesale-copied into a new run's tmp space; the new run materializes its own `workspace_final/` at end). Acceptable cost for the audit-trail benefit.
- **Negative — hard to reverse**: Once Resume Chains are in production, switching to mutate-in-place would break all archived chain links and conflate prior-run audit artifacts with subsequent legs.
## Alternatives Considered

- **Continuation Mode (mutate prior results dir)**: Rejected. The prior run's `workspace_final/`, snapshots, and `run_summary.json` are part of the audit trail; mutating them in place destroys post-hoc inspectability. A resumed run that later proves "the agent figured it out in the second half" would be indistinguishable from "the agent did it all in one shot" — and that distinction matters for understanding agent behavior. Also breaks the ability to recover a clean prior state if the resume leg itself goes off the rails.
- **Resume as a Snapshot-Selection Mode (continue running on the prior ****`.git`**** repo, no new run dir)**: Rejected. Snapshots are per-run intervals tied to a single Hard Timeout; merging them across runs is incoherent. Each Benchmark Run needs its own snapshot stream for telemetry to remain meaningful.
- **Promote tracking files (****`FILES_MODIFIED.json`****, ****`KEY_DECISIONS.md`****, ****`MODEL_AUDIT.jsonl`****, ****`RUN_DECISIONS.md`****) to the Workspace Contract** so the spec layer can do resume detection generically: Rejected (this round). Those files are conventions of one agent image's coordinator prompt, not properties of the Workspace Contract. Forcing all images to produce them is a large scope expansion. Resume detection done by the agent's prompt-layer logic is sufficient; the runner's only job is to stage the prior `workspace_final/` correctly. Revisit when multiple agent images converge on a common pattern.
- **Strict same-image resume (****`--image`**** must match prior)**: Rejected. Cross-agent resume is a genuinely useful forensics workflow ("Pi-blind got close, let me hand it to Claude-Code-tested for the home stretch"). Recording `resumed_image_changed: true` is enough to keep the audit honest. When leaderboard policy is formalized, cross-image legs are likely never leaderboard-valid, but that's a leaderboard concern, not a CLI restriction.
- **`--image`**** always required on resume (no defaulting)**: Rejected. Most resumes are "same agent, more time." Defaulting to the prior image makes the CLI ergonomic for the common case; explicit override remains available.
- **Strict refuse on snapshot-fallback prior runs**: Rejected. The most common reason to resume is "engine broke right at the end, fallback rolled back 15 minutes, give me more time to fix it properly." Refusing fallback-affected resumes would kill the main use case. The Resume Preamble's disclosure line keeps the agent informed without blocking the workflow.
