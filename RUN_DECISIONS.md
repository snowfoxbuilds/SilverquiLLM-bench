# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Item 1: Wire up workspace reference material correctly
- **Context**: Reviewer flagged that initial implementation kept `engine_api.md` and `base_classes.py` staged to avoid breaking pre-existing tests.
- **Decision**: Fully removed per TODO spec. Updated pre-existing tests to match new contract.
- **Reasoning**: The TODO is explicit. Keeping stale files staged (even without prompt reference) allows agents to discover and use them. Clean removal is correct.
- **Impact**: `silverquillm/workspace.py`, `docs/specs/WORKSPACE-CONTRACT.md`, `tests/test_workspace.py`, `tests/test_workspace_reference_material.py`.
