# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Spec deviation: Item 2 — Move rulebook.md into the workspace
- **TODO spec expected**: `git mv` an existing `rulebook.md` to `benchmarks/sos/workspace/rulebook.md`.
- **Actual codebase state**: No `rulebook.md` existed anywhere in the repo.
- **What was implemented instead**: Authored a new comprehensive MTG rules reference at `benchmarks/sos/workspace/rulebook.md`.
- **Impact**: `benchmarks/sos/workspace/rulebook.md` (new file). No history to `--follow` since it was created fresh.
