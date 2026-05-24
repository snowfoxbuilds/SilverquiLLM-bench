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

## Test failure: Item 5 — Move cards/ and normalize SOS stubs
- **Failing tests**: test_old_cards_directory_does_not_exist, test_no_stale_cards_imports_outside_cards_package, 15x test_card_impl_defines_cardimpl_subclass
- **Tester's intent**: Verify cards/ fully relocated, no stale imports, all SOS stubs define a CardImpl subclass
- **Implementer's approach**: Moved cards/ and updated imports, but left `cards/stubs` behind, missed 3 files with stale imports, and SOS stubs (soa_*) lack `from benchmarks.sos.workspace.engine.card import CardImpl` import
- **Coordinator decision**: fix implementation
- **Reasoning**: The test requirements match the TODO spec exactly; the implementation has gaps
