# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Wire up workspace reference material correctly

### Tests
- `tests/test_workspace_reference_material.py` — Validates rulebook, rules_overview, hard errors on missing sources, prompt text, and module constants

### Implementation
- `silverquillm/workspace.py` — Changed _RULEBOOK_SRC to comprehensive_rules.txt, added _RULES_OVERVIEW_SRC, reduced _REFERENCE_DOCS to only test_utils.md, removed stub fallback (hard error for all sources), updated _PROMPT_TEXT
- `docs/specs/WORKSPACE-CONTRACT.md` — Added rules_overview.md, removed engine_api.md and base_classes.py from workspace layout

