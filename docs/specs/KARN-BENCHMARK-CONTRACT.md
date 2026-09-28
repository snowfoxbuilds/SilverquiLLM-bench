Status: DRAFT
Last updated: 2026-09-26

# Karn Benchmark Contract

The bench consumes Karn v4 Construct Definitions through an independent execution host and evaluates implementations produced in the Workspace.

## Context

Karn owns the runnable definition and its build process.
The bench owns Benchmark Runs, task presentation, harvesting, Audited Eval, and observations used to learn from runs.
This page defines the bench's consumer contract; Karn's [Construct Contract](https://github.com/snowfoxbuilds/ozolith/blob/main/docs/specs/CONSTRUCT-CONTRACT.md) and [Construct Wire Format](https://github.com/snowfoxbuilds/ozolith/blob/main/docs/specs/CONSTRUCT-WIRE.md) own the producer interface.

## Design

### Purpose and retained observations

The goal of this integration is to collect data, learn from it, and improve candidates and benchmark tooling (grilling 2026-09-26).
It does not build a leaderboard eligibility system.
Completed, unsuccessful, interrupted, and partially observed runs remain useful evidence.
Record what ran, the available implementation and grades, Estimated Cost, Agent Turns, execution outcome, and observation completeness without reducing those facts to a single eligibility verdict.
Missing measurements are explained; they do not become zero and do not cause the available data to be discarded.

The analyst chooses comparisons and filters appropriate to the question being investigated.
Collection and retention do not depend on a publication or leaderboard gate.
For Karn v4 execution and observations, this page takes precedence over the older entrypoint-specific runner and telemetry descriptions.

### Candidate and build boundary

A Karn Benchmark Candidate is the selected immutable image paired with its v4 Construct Definition.
The complete definition matters: different runtime selections can use the same image.
The bench verifies the supplied definition and selected image before execution and records the selected runtime configuration.

Building is an explicit operation completed before the Benchmark Run begins (grilling 2026-09-26).
Karn resolves and builds the candidate; the bench consumes the resulting build output and does not rebuild from a recipe when a queued run starts.
Image and definition selection are fixed for that run, and build time is outside its execution budget.
Recipes and other build sources provide provenance; they do not substitute for the artifact actually executed.

### Independent execution

The bench launches the candidate directly, without an Ozolith Node Daemon (grilling 2026-09-26).
The bench owns scheduling, Workspace staging, User Prompt delivery, run launch, timeout enforcement, harvesting, and evaluation.
Karn configuration selects the container command, initializer, bootstrap, declared mounts and files, and required runtime facilities.
The benchmark host honors that selection.

Karn allows an Automaton to omit a polling controller (grilling 2026-09-26).
A controller is needed for automatic scheduling, not direct execution; controller-free execution requires no new wire-format field.
Externally launched execution does not suppress authentication or other selected lifecycle hooks.

The first supported facilities are ordinary Docker, account bootstrap, temporary Workspace/input/output mounts, Codex and Claude subscription login, and restricted networking for model and authentication access (grilling 2026-09-26).
Admission is not tied to a hardcoded model list.
The integration does not require an exhaustive rejection layer for every facility outside this initial implementation (grilling 2026-09-26).
The bench does not create a production issue claim or acquire authority to publish a pull request merely to execute a benchmark task.

### Implementation-only runs

A Benchmark Run in the new integration asks the candidate to implement the benchmark's problem set in its Workspace (grilling 2026-09-26).
The candidate need not produce a PR title, PR description, Decisions Section, commit message, or structured Implementer proposal.
Missing PR metadata is not a contract failure.
The bench imposes no production test, documentation, or lint workflow gate before accepting the implementation for evaluation.

Audited Eval grades the harvested Workspace against the host-side grading suites.
Candidate-written tests are artifacts and do not replace the grading suites.
The candidate may run available tests while implementing; iteration remains the candidate's responsibility.
Container termination and declared result files describe execution, while Audited Eval describes implementation correctness.

### Grading isolation

Grading imports and runs code the candidate wrote, so it never executes on the benchmark host.
Every engine-viability probe and grading pass runs in a bench-owned grader image, built explicitly and referenced by image ID, with no network, the operator's UID, a read-only root, dropped capabilities, resource limits, an allowlisted environment, and read-only mounts of only the selected Workspace, SilverquiLLM, and the grading inputs.
A run refuses before launch when the grader image is missing; it never builds or pulls it.
Nothing is mounted writable: the result returns as one size-capped, framed line on the container's stdout and is untrusted data, accepted only in the exact evaluation shape with bounded counts; a timeout, failure, oversized or rejected output records absent grades with the reason.
Each Run Record states its grading isolation and grader image ID.
Isolation protects the host's files, credentials, and network; it does not make scores tamper-proof, because candidate code shares the process that counts its results.

Planning and task guidance belong to each benchmark's instruction data, including the distinct hob-easy, hob-medium, and hob-hard benchmarks (grilling 2026-09-26).
New Karn runs have no separate basic/planned task-variation selector.
The benchmark's own guidance determines what the candidate is asked to do; historical Benchmark Mode values retain their original meaning.

### Subscription authentication

The first usable integration supports Codex subscription authentication (grilling 2026-09-26).
Resuming benchmarking does not require switching the Reference Candidate to separately billed API-key authentication.
The benchmark host reuses the existing Karn login plugin for preparing authentication before launch and persisting refreshed authentication after container stop (grilling 2026-09-26).
The bench supplies its host integration and does not replace the plugin's authentication parsing, refresh persistence, or recovery behavior.
The first real run validates this integration with a real device-authorization enrollment; the bench does not further replicate Karn's Node Daemon secret store, setup marker, or process environment, none of which the plugin relies on (grilling 2026-09-26).
As the Node Daemon does, the host kills a plugin process whose request timed out rather than reading its late reply, and admits the plugin's returned mounts only as an extension of those it passed: the passed mounts unchanged, each new source inside that plugin's own state directory, and no target overlapping another (grilling 2026-09-26).

Claude subscription authentication mirrors Codex through Karn's `karn-claude-login` plugin (grilling 2026-09-28).
The host accepts exactly the `karn-codex-login` and `karn-claude-login` plugins and refuses any other.
A Claude profile is enrolled through a fresh `claude auth login` session under the plugin's setup, and the operator's own Claude Code files are never copied into it.

Authentication values stay outside candidate identity and published results.
Cleanup retains authentication that has not been persisted until persistence succeeds or the operator explicitly abandons it, following Karn's [Login Plugins](https://github.com/snowfoxbuilds/ozolith/blob/main/docs/specs/LOGIN-PLUGINS.md) contract.
Authentication storage is distinct from the Workspace and from retained benchmark evidence.

A named Login Profile selects subscription authentication independently of candidate identity and can be reused across candidate variants and batches (grilling 2026-09-26).
A profile is enrolled through a fresh login session, so it holds its own session and refresh chain, separate from the operator's own login, whose files are never copied into it (grilling 2026-09-26).
Each run starts with fresh native state; only authentication persists between runs.
At most one runner on the host may use a login at a time because concurrent token refresh can invalidate the shared authentication (grilling 2026-09-26).
Use the existing local login binding and a host-local exclusive runner lock, shared by direct runs, scheduler execution, and enrollment.
Exclusive ownership covers authentication preparation, execution, and final authentication harvest; recovery confirms that a prior runner's container has stopped before reusing its login.
No new account registry, credential-deduplication system, or cross-host coordination is part of this integration (grilling 2026-09-26).
Each host benchmarks independently.

### Execution budget

The execution budget starts at container start and includes initialization (grilling 2026-09-26).
The default safety ceiling is 24 hours and can be changed explicitly for a run.
Builds, login enrollment, host staging, and post-run grading are outside that budget.
A definition timeout shorter than the requested Benchmark Run budget is refused before launch; the operator selects an explicit compatible definition.
The host enforces the requested run deadline when the definition permits a longer run.

Wall-clock observations support deadline enforcement and diagnosis, but are secondary comparison metrics (grilling 2026-09-26).
Estimated Cost and Agent Turns are primary efficiency measurements and are recorded rather than used as stopping limits in the first integration (grilling 2026-09-26).

### Efficiency measurements

An Agent Turn is one model response or one tool call (grilling 2026-09-26).
The total is the sum of response and tool-call counts; both component counts are retained.
Include descendant-agent and compaction responses and descendant-agent tool calls.
Count each logical response and call once, rather than counting streaming fragments or both start and completion notifications.
A tool call that reports an error remains a tool call.
Native user-request turns, such as Codex's, are a different observation and cannot substitute for this metric.

Estimated Cost is API-equivalent USD computed from observed token usage and a versioned model-price table (grilling 2026-09-26).
Retain the reported model, token breakdown, price-table version, and pricing assumptions so the estimate can be reproduced.
The cost breakdown tallies input tokens by type, for every provider: uncached input, cache reads, and cache writes, with 5-minute and 1-hour writes separate where the provider prices them differently; each type carries its token count and its cost beside the output tokens (grilling 2026-09-28).
Usage is normalized into these types from each provider's own convention: OpenAI's input total includes cached tokens, while Anthropic's input count excludes cache reads and writes.
The estimate is a comparison of resource usage and does not claim to allocate the actual subscription charge to the run.
Missing or incomplete observations remain explicitly missing or incomplete, rather than becoming zero.

The integration qualifies response, tool-call, and usage capture against the pinned native CLI.
The current stock result file's usage:null and whole-request turn.completed events do not establish the required measurements.
Codex's existing opt-in telemetry is an implementation path to qualify without changing the task into a custom agent workflow.
Claude Code mirrors it (grilling 2026-09-28): the session transcript under its config directory is the durable source that recovery also reads, and its OpenTelemetry request and tool events cross-check it.
The transcript's format is internal to Claude Code, so each pinned Claude Code version is qualified before its measurements count as complete.

### Outcomes and retained evidence

Execution outcome, grading, and measurement completeness are separate observations (grilling 2026-09-26).
The bench harvests available work after confirming that the workload has stopped, including useful partial work.
Retain the final Workspace and existing Output Snapshot/fallback provenance so analysis can identify any recovered state used for grading.

| Observed outcome | Retained evidence |
| --- | --- |
| Execution budget exhausted | Deadline stop reason, partial implementation and grading, and available usage |
| Candidate exits nonzero after starting work | Exit status, available diagnostics, partial implementation and grading, and available usage |
| Authentication, launch, or host failure | Known failure stage and diagnostics, plus any implementation, grading, or usage obtained |
| Operator interruption | Explicit interruption reason and the available implementation, grading, and usage |

An unknown failure cause remains unknown instead of receiving a guessed attribution.
If grading could not run, record why; an absent evaluation is different from an evaluated implementation scoring zero.
Incomplete cost or turn measurements are labeled as such alongside the available values.
No eligible/ineligible decision is required to retain or analyze these observations.
A missing result file after a forced stop does not prevent partial grading.
The stock entrypoint's result file is runtime evidence, not required model-authored PR metadata, and remains available to authentication exit hooks before cleanup.

### hob-medium workstream

Completing hob-medium is part of this workstream, including its missing Test Oracle Workspace and all five selected Test Oracle Impls (grilling 2026-09-26).
[HOB Benchmarks](HOB-BENCHMARKS.md) owns the selected Card Pool, benchmark assets, instruction data, and oracle-first validation requirements.
The existing smoke benchmark exercises the integration before hob-medium runs collect implementation and efficiency data.
The workstream also covers the CLI and batch paths that retain those observations as Run Records.

### Operator entrypoints and records

`silverquillm run` and `silverquillm scheduler` share the same staging, execution, observation, harvesting, and grading lifecycle, and `silverquillm recover` settles an interrupted run from its retained evidence without rerunning work.
The `login` command enrolls a named host-local Login Profile through the selected existing plugin.
SilverquiLLM runs a completed Karn build by itself; the vendored v4 construct contract is the only thing it takes from Karn, and no Ozolith package is involved.
[Operator instructions](../KARN-BENCHMARKING.md) show explicit builds, direct runs, batches, and recovery.

New immutable Run Records use schema 2 and the `karn-v4` identity scheme.
They retain the full selected definition, execution observations, three independent grading dimensions, measurement completeness, and artifact pointers.
An unexecuted grading dimension has null counts and pass rate with a reason.
Coverage names tested and uncovered cards, so an incomplete FDN suite does not imply full FDN coverage.

Workspace snapshots contain only workspace files and exclude authentication state.
Final evidence includes a Git bundle of available referenced commits, produced through a clean repository that excludes candidate hooks and credential configuration; an unavailable history is recorded explicitly.
The runner preserves the final workspace even when its engine is unusable; fallback selects the newest retained snapshot whose engine passes the same viability check, and records the selected path and reason.
A fallback grade describes that snapshot, while the execution outcome continues to describe the actual run.

### Historical evidence

Existing Run Records retain their original identities and interpretation.
A historical Candidate Bundle does not become a Karn v4 Construct Definition by relabeling it.
The vendored [Bench Contract](BENCH-CONTRACT.md) remains the reference for the legacy Candidate Bundle API.
Candidate Bundles can no longer be executed; their records stay readable without Ozolith.
This consumer contract governs Karn v4 execution.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-004](../adr/ADR-004-docker-agent-containers-replace-python-adapters.md) | The host stages, launches, harvests, and evaluates isolated candidates |
| [ADR-005](../adr/ADR-005-in-place-workspace-engine-with-snapshot-fallback.md) | Preserve final Workspace and snapshot/fallback evidence |
| [ADR-012](../adr/ADR-012-independent-host-for-karn-benchmark-candidates.md) | Karn builds candidates and an independent bench host executes their declared contract |
| [ADR-013](../adr/ADR-013-grading-runs-in-a-network-less-grader-container.md) | Candidate code executes only in a network-less grader container |
| [ADR-014](../adr/ADR-014-silverquillm-runs-karn-constructs-without-ozolith.md) | SilverquiLLM runs Karn constructs without Ozolith; Candidate Bundle execution is removed |
