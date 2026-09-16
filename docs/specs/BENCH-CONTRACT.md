Status: DRAFT
Last updated: 2026-09-16

# Bench Contract

SilverquiLLM-bench evaluates standalone Karn Construct Definitions using its own Docker host and benchmark workflow.

## Context

A reproducible candidate identifies both the selected definition and immutable image bytes.
The benchmark owns prompts, gates, evaluation and eligibility; these are independent of the Ozolith runtime.
The cross-project ownership boundary is described in [Ozolith's Bench Contract](https://github.com/snowfoxbuilds/the-ozolith/blob/main/docs/specs/BENCH-CONTRACT.md).

## Design

### Definition and image admission

Karn owns the versioned Construct Definition decoder and execution contract.
This consumer accepts explicit definition versions 1, 2 and 3, using their respective Karn schemas without reinterpretation.
`silverquillm run --candidate` accepts a definition JSON file, a directory containing `definition.json`, or a curated directory containing `bundle/definition.json`.
Symlinked definition paths, malformed documents and credential-shaped embedded values refuse.
Payload schemas follow Karn’s JSON Schema 2020-12 contract: active references use local fragments, unsupported dialects and external active references refuse during definition admission, and annotations remain data.
The benchmark also validates with a closed registry that cannot read host files or fetch remote schemas even when called without admission.
Historical `candidate.json` bundles are preserved for historical evidence and are not executable inputs to this host.

The selected immutable image must already exist in the chosen local Docker Engine.
The host verifies its Linux platform and immutable ID or matching repository digest, then launches by actual image ID.
It does not build, pull, inspect reverse descriptor labels, require an Ozolith package, or demand a Config Repo, Node receipt or promotion history.
Two definitions can select identical image bytes while choosing different runtime behavior.
Local availability is neither a dirty flag nor a leaderboard disqualification.

### Candidate identity and evidence

New candidates use identity scheme `karn-definition-v1`.
The Candidate Hash is SHA-256 of canonical JSON containing exactly `scheme`, `definition_digest` and `image_digest`.
`definition_digest` is Karn's digest of the complete canonical definition; `image_digest` is the immutable digest selected by its image reference.
The definition contains the reference, so distinct references remain distinguishable even when their digest components match.
The actual Engine image ID is recorded as a runtime observation.
Definition changes, including initialization and runtime input declarations, change candidate identity.

New Run Records use record schema 2.
Historical schema-1 `legacy` and `ozolith-v1` records retain their original readers, serialization and hash formulas.
No historical identity is silently upgraded or relabeled.
Run evidence records the benchmark and mode, supplied input hashes, definition version, actual image, allocated UID/GID, runtime capabilities, process outcome, gate result, proposal status and grading result.
Runtime-installed software is not proven by the original image digest; the ephemeral gate snapshot records its own image ID.
Absent model/tool observations are not invented, and provider model names are not attestations.

### Supported host capabilities

The independent host requires rootful Linux Docker without user remapping and a local Unix socket.
The default identity is the invoking account's UID/GID; an explicit container user must match that account.
Karn's configured initializer, initializer runner and identity-v1/v2 bootstrap run as declared.
The host validates the current launch's identity handoff before accepting completion.

Supported definitions are Docker Automatons with `none` or `open` networking and launch-private runtime mounts.
The benchmark supplies one writable workspace, declared prompt input and writable proposal output; additional launch-private mounts use host-owned locations under that run.
Mount targets and file paths are declaration-owned; host source paths are operator-owned.
Host binds, host-only exposure, persistent mounts, overlapping mounts, restricted networking, Vehicles, host plugins, retained authentication lifecycle, provider credentials and relay delivery refuse before launch.
These are this host's capability limits, not restrictions on Karn definitions or Ozolith.
The host never deletes unsupported retained authentication state or pretends it performed an omitted lifecycle.

Direct raw credentials can use environment or file delivery.
A logical raw reference selects its uppercase environment name with dots and hyphens replaced by underscores; ambiguous normalized bindings refuse.
Missing bindings refuse, values never enter command-line arguments or evidence, and captured output is redacted before persistence.
Credential files are private launch resources removed only after all owned containers are confirmed absent.

### Benchmark-owned workflow

The benchmark stages its own synthetic issue and context, preserving basic/planned task semantics.
Planned mode adds the existing short-plan instruction; both modes receive the same benchmark problem set and proposal requirements.
The template and schema-1 Output Proposal parser are benchmark-owned conformance fixtures derived from the historical workflow.
The substantive task, Decisions, no-change and git/gate constraints are retained; unavailable formatter commands and live-upstream claims are replaced with explicit JSON file and synthetic-context instructions.
The host renders the declared input path and explicitly gives the declared proposal output path.
No keeper, jobs channel, production workflow package or live GitHub context is required.

The configured main process runs to container exit.
Timeout, nonzero exit, missing output and invalid output remain distinct failures; a stopped container alone is not a successful answer.
Proposals retain title, description, commit-message, Decisions Section and no-change reasoning requirements.
The driver composes provenance and uses a separate, unmounted bare git repository for its own commits.
Candidate git hooks/configuration never direct host git operations.

Gate commands remain in isolation and run in test, docs, lint order, then any additional named steps.
The gate uses a private snapshot of the stopped workload so initialized tools and accounts remain available.
Each command runs in an owned container with the same controlled mount mappings; commands never execute in the driver process.
The benchmark's audited evaluator and eligibility derivation remain authoritative and unchanged.
Confirmed-stopped partial work may be graded after a failed attempt; unevaluated work is explicitly marked unevaluated.

### Cleanup and scheduler recovery

Before creating resources, the host writes a private resource inventory beside the run artifacts.
It records the Docker Engine, ownership token, selected image, container identities and gate snapshot operation.
Cleanup verifies the entire inventory before mutation, stops and removes only matching owned containers, and removes the gate snapshot without pruning the selected image.
An uncertain operation retains its inventory and prevents grading or scheduler continuation until reconciliation confirms cleanup.
A replacement scheduler on the same host reconciles workload and gate resources before starting new work.
A replacement host requires the existing explicit cleanup acknowledgement; portable batch state never supplies arbitrary host paths.

### Promotion and publication

[Benchmark Candidates](BENCHMARK-CANDIDATES.md) owns curated source inventories, atomic promotion, batch state and transactional result publication.
A promoted source copy proves the selected definition bytes; it does not claim to reproduce or attest the image build.
Publication requires matching current candidate identity and source inventory, plus the existing whole-tree credential scan.
Eligibility is independently checked: ineligible results need the explicit publication override and remain excluded from leaderboards.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-008](../adr/ADR-008-resume-legs-are-independent-benchmark-runs.md) | Resume legs are independent runs and remain ineligible. |
| [ADR-011](../adr/ADR-011-three-tier-benchmark-locking.md) | Benchmark lifecycle governs when benchmark inputs may change. |
