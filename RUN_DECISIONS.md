# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Reviewer enhancement: Item 1 — Deletion detection in _check_violations
- **Reviewer comment (strict)**: _check_violations doesn't detect deletions of protected files. Deleting protected files is contamination too.
- **Coordinator decision**: Accept reviewer's suggestion. Add deletion detection.
- **Reasoning**: The TODO spec only mentions "modified" and "created", but the purpose of the feature is contamination detection. Deletion is a valid contamination vector that should be caught. Small extension that fits the spirit of the feature.
- **Impact**: benchmark/agent_session.py, tests/test_check_violations.py
