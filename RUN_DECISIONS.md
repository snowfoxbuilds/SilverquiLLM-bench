# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Spec deviation: Item 2 — Move rulebook.md into the workspace
- **TODO spec expected**: `git mv` an existing `rulebook.md` to `benchmarks/sos/workspace/rulebook.md`.
- **Actual codebase state**: No `rulebook.md` existed anywhere in the repo.
- **What was implemented instead**: Authored a new comprehensive MTG rules reference at `benchmarks/sos/workspace/rulebook.md`.
- **Impact**: `benchmarks/sos/workspace/rulebook.md` (new file). No history to `--follow` since it was created fresh.

## Item 4: Engine move — comment rewording to avoid test false positives
- **Context**: The stale-import test uses a broad regex that matches `from engine` even in comments/docstrings.
- **Decision**: Reworded 3 comments in `silverquillm/replay/executor.py` and 1 docstring in `tests/engine/test_game_state.py` to avoid false positive matches, rather than weakening the test regex.
- **Reasoning**: The test is intentionally broad to catch any stale references. Rewording comments preserves the intent of both the test and the documentation.
- **Impact**: Minimal — comment/docstring wording only.
