# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Reviewer enhancement: Item 1 — Deletion detection in _check_violations
- **Reviewer comment (strict)**: _check_violations doesn't detect deletions of protected files. Deleting protected files is contamination too.
- **Coordinator decision**: Accept reviewer's suggestion. Add deletion detection.
- **Reasoning**: The TODO spec only mentions "modified" and "created", but the purpose of the feature is contamination detection. Deletion is a valid contamination vector that should be caught. Small extension that fits the spirit of the feature.
- **Impact**: benchmark/agent_session.py, tests/test_check_violations.py

## Spec deviation: Item 3 — load_prototype_cards return type
- **TODO spec expected**: `load_prototype_cards(prototype_path: str) -> list[dict]` but description says "extract collector numbers, and return them"
- **Actual decision**: Return `list[str]` (collector numbers), not `list[dict]` (raw prototype entries)
- **What was implemented**: Changed return type to `list[str]`, extracting collector_number from each entry
- **Reasoning**: The description "extract collector numbers, and return them" is the intended behavior. The type annotation `list[dict]` is inconsistent with the description. Returning just collector numbers makes the API composable — `filter_by_prototype` can directly pass to `filter_by_collectors`.
- **Impact**: benchmark/card_loader.py, tests/test_card_loader.py
