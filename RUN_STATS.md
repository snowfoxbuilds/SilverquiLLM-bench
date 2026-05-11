# Run Stats

**Skill**: execute-todo-with-subagents
**Reviewer model**: GPT-5.4 (via `Reviewer` custom agent)
**Started**: 2026-05-11T06:27:14Z
**Finished**: 2026-05-11T14:55:44Z
**Total duration**: 8h 28m 30s
**Total duration (seconds)**: 30510

## Summary

- TODO items completed: 15
- Items requiring test dispute: 3
- Items requiring review revision: 14
- Items with coordinator arbitration: 15
- Commits: 19 after this file is committed
- RUN_DECISIONS entries: 24
- KEY_DECISIONS entries added: 12
- Test quality audit: 0 added, 5 fixed, 0 deleted
- Test suite result: non-audited and FDN audited tests passing; SOS audited tests collect and run with expected stub-behavior failures only

## Tokens (subagents)

- Total Tester tokens: null
- Total Implementer tokens: null
- Total Reviewer tokens: null
- Total across all subagents: null
- Coordinator tokens: null

Token counts were not exposed by the subagent orchestration layer. Durations below are aggregated from `/tmp/execute-todo-with-subagents-phase6-20260511-062714/run-stats.md`.

## Per-item breakdown

| TODO item | Implementer | Tester | Reviewer | Test disputes | Review revisions | Duration (s) |
|-----------|-------------|--------|----------|---------------|------------------|--------------|
| Item 1: Include Mystical Archives | null | null | null | 0 | 2 | 854 |
| Item 2: Include Special Guests | null | null | null | 1 | 2 | 1101 |
| Item 3: Enforce SOS base cutoff | null | null | null | 0 | 2 | 677 |
| Item 4: Regenerate SOS classification/specs | null | null | null | 0 | 1 | 1105 |
| Item 5: Per-card audited test infrastructure | null | null | null | 0 | 2 | 2288 |
| Item 6: Generate SOS stub card classes | null | null | null | 1 | 2 | 1758 |
| Item 7: FDN audited tests batch 1 | null | null | null | 0 | 2 | 1474 |
| Item 8: FDN audited tests batch 2 | null | null | null | 1 | 2 | 3042 |
| Item 9: FDN audited tests batch 3 | null | null | null | 0 | 1 | 1889 |
| Item 10: FDN audited tests batch 4 | null | null | null | 0 | 1 | 2502 |
| Item 11: FDN audited tests batch 5 | null | null | null | 0 | 1 | 1925 |
| Item 12: SOS audited tests batch 1 | null | null | null | 0 | 1 | 1819 |
| Item 13: SOS audited tests batch 2 | null | null | null | 0 | 1 | 2181 |
| Item 14: SOS audited tests batch 3 | null | null | null | 0 | 1 | 1827 |
| Item 15: Wire per-card audited eval | null | null | null | 0 | 1 | 882 |
| Dir summaries | null | - | - | - | - | 185 |
| Test audit | - | null | - | - | - | 534 |

## Validation snapshot

- Non-audited suite: 4359 passed
- FDN audited suite: 1487 passed
- SOS audited suite: 2995 passed, 994 expected failures against intentionally behavior-empty stubs
