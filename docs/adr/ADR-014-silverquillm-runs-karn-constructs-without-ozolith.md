Status: ACCEPTED
Date: 2026-09-26

# ADR-014: SilverquiLLM Runs Karn Constructs without Ozolith

## Context

The bench ran candidates two ways: Karn v4 constructs through its own independent host (ADR-012), and Candidate Bundles through Ozolith's implementer Run Contract, bundle verifier and verified build.
The Candidate Bundle path made four pinned `theozolith-*` packages a runtime dependency, and its batch scheduler and queue views pulled them into commands Karn operators use every day.
The bench's purpose is collecting Karn run data, and a second execution lineage with its own identity, scheduler, promotion and publication gates doubled the surface to keep correct.

## Decision

SilverquiLLM takes a completed Karn build (a v4 Construct Definition and its exact image) and runs, grades, records and recovers it by itself.
The Karn construct contract, vendored as the v4 schema, is the only thing taken from Karn; no command, module or retained script in the default install imports a `theozolith-*` package, and a test refuses such an import anywhere.

Candidate Bundle execution is removed: its run driver, job-directory staging, Output Proposal handling, contract pin, bundle ingestion, batch scheduler, promotion and publication scripts, and the checked-in `candidates/` tree.
The Karn commands own the top level (`run`, `scheduler`, `login`, `queue ls`, `top`).
The pre-Karn `--image` entrypoint lineage, which never depended on Ozolith, stays available under `silverquillm legacy` for its historical run directories.

Historical evidence keeps its meaning: schema 1 Run Records, including `legacy` and `ozolith-v1` identities, stay readable without Ozolith, and every `ozolith-v1` record carries its vendored bundle.
Batch files and state in the removed format are reported as unsupported and never rewritten or run.

## Consequences

- **Positive**: A plain `pip install` runs every command; the runner and scheduler have no external execution-contract dependency.
- **Positive**: One execution lineage, one batch format and one record schema for new data.
- **Negative**: A Candidate Bundle can no longer be run, promoted or published; running an old candidate means rebuilding it as a Karn construct.
- **Negative**: New `ozolith-v1` records cannot be produced, and existing ones cannot be re-verified against Ozolith's verifier.
- **Neutral**: The vendored Bench Contract remains the reference for interpreting historical Candidate Bundle records.

## Alternatives Considered

- **Keep Candidate Bundle execution behind an optional `legacy` extra**: Rejected because shared views still reached Ozolith through it, and it would keep a second lineage alive for data the bench no longer collects.
- **Quarantine it under a `legacy` command group and delete it later**: Rejected in favor of a clean break while the Karn stack is still unmerged.

## Relevant PRs

- #85 — Removes the Candidate Bundle path and promotes the Karn commands.
