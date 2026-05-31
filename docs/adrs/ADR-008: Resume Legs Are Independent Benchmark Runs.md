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

Resume Legs are never leaderboard-valid: any run with `resumed_from` set has `run_summary.json.leaderboard_valid = false`, since legs inherit prior-leg workspace state and are not head-to-head comparable with fresh full-set runs. (Updated 2026-05-30 — the original ADR deferred this; the policy is now settled.)

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
## Implementation Decisions (consolidated from BENCHMARK-RUNNER, 2026-05-30)

These detailed resume decisions were moved here from [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) → Decisions to keep the runner spec lean. They refine this ADR and ADR-009; the resume *behavior* contract still lives in [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) → Resume.

- **Resume is a CLI subcommand**: `silverquillm resume <prior-run-id>` creates a fresh Benchmark Run that stages from the prior run's `workspace_final/`. Each Resume Leg is an independent Benchmark Run — own `run_name`, results directory, Hard Timeout, snapshots, and evaluation. Legs are linked via `resumed_from`; the sequence is a Resume Chain. Mutating the prior run dir in place was considered and rejected for audit-trail integrity.
- **Resume staging skips ****`git init`**: Resume staging copies the prior `workspace_final/` wholesale into the per-run tmp directory and overwrites only `prompt.md` and `run_manifest.json`. No `git init`, no initial commit — the prior `.git` history (host snapshots and any agent commits) is preserved as-is so the resumed agent can inspect prior work.
- **Resume ****`--image`**** defaults to prior, override allowed**: If `--image` is omitted, the runner reads prior `run_summary.json.docker_image` and uses it. Explicit override is allowed; the runner records `resumed_image_changed: true` and adds a Resume Preamble line warning the new agent that workspace tracking files may follow the prior agent's conventions. Cross-image resume is mechanically supported but expected to be leaderboard-invalid.
- **Resume source must be a viable ****`workspace_final/`**: Refuse resumes when prior `run_status` is `no_viable_output_produced` or when `workspace_final/` is missing. Accept resumes from runs that used snapshot fallback; the Resume Preamble discloses the fallback so the agent knows its inherited state was rolled back. A future `--from-snapshots` opt-in flag may be added to recover from non-viable runs.
- **Runner appends a Resume Preamble to the User Prompt**: On resume runs, the runner appends a short preamble informing the agent that this is a resume of `<prior-run-id>`, that prior tests/implementations may exist, and that the `.git` history records prior commits. Conditional lines disclose snapshot fallback (when used) and image change (when `--image` differs). The preamble is image-agnostic.
- **Resume Legs are never leaderboard-valid**: Any Benchmark Run with `resumed_from` set has `run_summary.json.leaderboard_valid = false`. Resumes inherit prior-leg workspace state (and possibly a different image or a snapshot-rolled-back engine), so they are not head-to-head comparable with fresh full-set runs.
- **Resume accepts path or run-id, with unique-match glob**: The `resume` and `chain` subcommands accept either a full results path or a bare `run-id`. ID mode globs `docker/*/results/<arg>/` and requires exactly one match (0 or 2+ errors loudly). Image is cross-checked across `<image-dir>`, `run_manifest.json`, and `run_summary.json`; any disagreement aborts.
- **Resume ****`--timeout`**** is required, never defaulted**: `--timeout` is required on every `silverquillm resume`, mirroring `silverquillm run` — each Resume Leg's budget is an independent deliberate choice. When omitted, the error message reads the prior leg's manifest and summary to suggest `--timeout` and wall-clock-used. Defaulting to the prior leg's timeout was rejected because it hides a budget choice with downstream scoring implications.
- **Snapshot fallback detection reads the ledger, not ****`run_summary.json`** (see ADR-009): The Resume Preamble's snapshot-fallback disclosure and cited `snapshot_utc` come from the prior run's snapshot ledger, which survives harvester failure, not the post-hoc summary.
- **Missing prior ****`run_summary.json`**** requires explicit opt-in**: If prior `run_manifest.json` is missing, resume is refused outright. If only `run_summary.json` is missing, resume requires `--force-missing-summary`, which skips the `no_viable_output_produced` refusal check, drops the wall-clock-used hint, and adds a Resume Preamble line disclosing harvester failure.
- **Resume Chains have a minimal reader from day one**: `silverquillm chain <run-id>` walks `resumed_from` pointers and prints a one-screen table of legs. Cycle detection errors loudly. The reader exists so `resumed_from` always has a consumer — telemetry fields without readers drift. Per-leg `git log` rendering and chain-level aggregation are out of scope for v1.
- **Resume Chains have no maximum depth**: Resuming a Resume Leg is identical to resuming a fresh run; the chain reader walks ancestry through any number of `resumed_from` links.
- **Resume Chains are trees; forks are allowed silently**: The same prior run may be resumed multiple times, producing sibling legs with the same `resumed_from`. `resumed_from` stays scalar; there is no merge semantic. Refusing forks by default was rejected because intentional A/B forking is legitimate. Forward-walking to find descendants is v2 scope.
- **Cross-image resume emits stderr warning, never blocks**: When `--image` differs from prior, the runner prints a stderr warning with both image names, the prior leg's `run_status`, and wall-clock-used. An `--allow-image-change` flag would be redundant friction, but a visible diff prevents the typo case.
- **Resume ****`--cards`**** is per-leg, no inheritance**: `--cards` on resume defaults to none (full set), with no inheritance from the prior leg's `card_filter` — mirroring the `--timeout` policy. When this leg's filter differs from prior, the Resume Preamble discloses inherited-but-out-of-scope state.
- **Resume Preamble is placed at the top of ****`prompt.md`**** under a ****`## Resume context`**** heading**: Followed by a `---` separator and the original User Prompt body. Top placement gives context-before-task; the heading makes the Preamble grep-able. Bottom placement and inline markers were rejected.
## Alternatives Considered

- **Continuation Mode (mutate prior results dir)**: Rejected. The prior run's `workspace_final/`, snapshots, and `run_summary.json` are part of the audit trail; mutating them in place destroys post-hoc inspectability. A resumed run that later proves "the agent figured it out in the second half" would be indistinguishable from "the agent did it all in one shot" — and that distinction matters for understanding agent behavior. Also breaks the ability to recover a clean prior state if the resume leg itself goes off the rails.
- **Resume as a Snapshot-Selection Mode (continue running on the prior ****`.git`**** repo, no new run dir)**: Rejected. Snapshots are per-run intervals tied to a single Hard Timeout; merging them across runs is incoherent. Each Benchmark Run needs its own snapshot stream for telemetry to remain meaningful.
- **Promote tracking files (****`FILES_MODIFIED.json`****, ****`KEY_DECISIONS.md`****, ****`MODEL_AUDIT.jsonl`****, ****`RUN_DECISIONS.md`****) to the Workspace Contract** so the spec layer can do resume detection generically: Rejected (this round). Those files are conventions of one agent image's coordinator prompt, not properties of the Workspace Contract. Forcing all images to produce them is a large scope expansion. Resume detection done by the agent's prompt-layer logic is sufficient; the runner's only job is to stage the prior `workspace_final/` correctly. Revisit when multiple agent images converge on a common pattern.
- **Strict same-image resume (****`--image`**** must match prior)**: Rejected. Cross-agent resume is a genuinely useful forensics workflow ("Pi-blind got close, let me hand it to Claude-Code-tested for the home stretch"). Recording `resumed_image_changed: true` is enough to keep the audit honest. When leaderboard policy is formalized, cross-image legs are likely never leaderboard-valid, but that's a leaderboard concern, not a CLI restriction.
- **`--image`**** always required on resume (no defaulting)**: Rejected. Most resumes are "same agent, more time." Defaulting to the prior image makes the CLI ergonomic for the common case; explicit override remains available.
- **Strict refuse on snapshot-fallback prior runs**: Rejected. The most common reason to resume is "engine broke right at the end, fallback rolled back 15 minutes, give me more time to fix it properly." Refusing fallback-affected resumes would kill the main use case. The Resume Preamble's disclosure line keeps the agent informed without blocking the workflow.
