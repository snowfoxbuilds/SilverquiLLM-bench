# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Item 1: Wire up workspace reference material correctly
- **Context**: Reviewer flagged that initial implementation kept `engine_api.md` and `base_classes.py` staged to avoid breaking pre-existing tests.
- **Decision**: Fully removed per TODO spec. Updated pre-existing tests to match new contract.
- **Reasoning**: The TODO is explicit. Keeping stale files staged (even without prompt reference) allows agents to discover and use them. Clean removal is correct.
- **Impact**: `silverquillm/workspace.py`, `docs/specs/WORKSPACE-CONTRACT.md`, `tests/test_workspace.py`, `tests/test_workspace_reference_material.py`.

## Item 2: --cards-aware status / summary / postmortem plumbing
- **Context**: Reviewer caught that filter comparison used directory names (from `card_loader.py` override) instead of numeric collector numbers from JSON.
- **Decision**: Added `json_collector_number` field to preserve original JSON value; dual-match logic supports both `--cards 1` (numeric) and `--cards soa_1` (dir-name).
- **Reasoning**: `card_loader.py` already overrides `collector_number` with directory name for filesystem operations. Adding a separate field is non-breaking.
- **Impact**: `silverquillm/card_loader.py`, `silverquillm/cli.py`.
