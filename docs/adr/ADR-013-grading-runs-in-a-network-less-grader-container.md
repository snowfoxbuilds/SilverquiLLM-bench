Status: ACCEPTED
Date: 2026-09-26

# ADR-013: Grading Runs in a Network-less Grader Container

## Context

Grading imports and executes the Python the agent left in its workspace: the engine-health probe imports the candidate engine, and every audited suite runs the candidate's cards on the candidate's engine.
Before this decision that code ran on the benchmark host as the operator, with the operator's full environment and network.
The candidate container is built to keep subscription authentication away from the model (restricted egress, redaction, a login mounted only during the run), but the refreshable login secret lives under the operator's state directory on the same host.
Code written inside the sandbox therefore reached the host at grading time.

## Decision

Candidate code executes only inside a grader container.
The container runs a bench-owned image pinned by base-image digest and hashed pytest requirements, built explicitly with `grader build` and referenced by image ID; a run refuses before launch when the image is missing and never pulls or builds it.
Each probe or grading pass runs with no network, the operator's UID and GID, a read-only root filesystem, all capabilities dropped, no privilege escalation, memory and process limits, a size-limited `/tmp`, and an allowlisted environment.
Only the selected workspace, SilverquiLLM's package, and the grading inputs the evaluation reads are mounted, read-only; one empty output directory is writable.
The host treats the container's output as untrusted data: one size-capped regular file, parsed as strict JSON and accepted only in the exact evaluation shape, with pass rates recomputed from counts.
A timeout, failed container, or rejected output records the run with absent scores and the reason, never zero.
Each Run Record states the grading isolation and grader image ID.

## Consequences

- **Positive**: A candidate cannot read the operator's login, environment, or files, cannot reach the network, and cannot alter the grading inputs or SilverquiLLM during grading.
- **Negative**: Grading requires Docker and a locally built grader image, and each probe or grading pass pays container start-up time.
- **Neutral**: Isolation protects the host, not score integrity: candidate code shares the pytest process that counts its results, so a hostile candidate can still misreport its own score.
- **Neutral**: The legacy `--image` lineage grades through the same container; its host-side engine-patch application stays on the host because applying a patch executes no candidate code.

## Alternatives Considered

- **Scrub the environment only**: removes inherited credentials but leaves the login secret file, the operator's files, and the network reachable. Rejected as a partial fix.
- **Grade in the candidate's own image**: no extra image, but the grader's interpreter and pytest would be candidate-controlled. Rejected.

## Relevant PRs

- #85 — Grades candidate work and probes engine health only in the grader container.
