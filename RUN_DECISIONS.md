# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Test failure: Item 1 — Remove --cards-dir and --engine-dir CLI flags
- **Failing tests**: test_signature_does_not_accept_cards_dir, test_signature_does_not_accept_engine_dir, test_harvest_signature_no_cards_dir
- **Tester's intent**: Verify parameters are fully removed from function signatures per TODO spec
- **Implementer's approach**: Kept cards_dir/engine_dir as optional params with None defaults for backward compatibility
- **Coordinator decision**: fix implementation
- **Reasoning**: The TODO spec explicitly says "Replace cards_dir and engine_dir parameters with hardcoded paths" and "Update stage_workspace() signature to stage_workspace(output_dir: Path, *, card_filter: list[str] | None = None)". The parameters must be fully removed, not made optional. Tests in the repo can be updated to use the new signature.
