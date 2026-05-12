# Run Stats

**Skill**: execute-todo-with-subagents
**Reviewer model**: GPT-5.4 (via `Reviewer` custom agent)
**Started**: 2026-05-12T16:32:39Z
**Finished**: 2026-05-12T20:33:13Z
**Total duration**: 4h 0m 34s
**Total duration (seconds)**: 14434

## Summary
- TODO items completed: 10 (items 7–16)
- Items requiring test dispute: 0
- Items requiring review revision: 8 (items 7, 8, 9, 10, 11, 14, 15, 16)
- Items with coordinator arbitration: 8
- Commits: 13 (10 feature/fix + 1 dir summaries + 1 test audit + 1 reset)
- RUN_DECISIONS entries: 9
- KEY_DECISIONS entries added: 2 (process-group termination, TESTING-CONVENTIONS)
- Test quality audit: 4 added, 5 fixed, 0 deleted
- Test suite result: passing (1861+ non-audited tests)

## Tokens (subagents)
- Total Implementer tokens: null (not observable per-invocation)
- Total Tester tokens: null (not observable per-invocation)
- Total Reviewer tokens: null (not observable per-invocation)
- Total across all subagents: null
- Coordinator tokens: null (not observable)

## Subagent Duration (seconds)
- Total Implementer: 5365s
- Total Tester: 6000s
- Total Reviewer: 1284s
- Total across all subagents: 12649s

## Per-item breakdown
| TODO item | Implementer (s) | Tester (s) | Reviewer (s) | Test disputes | Review revisions | Total (s) |
|-----------|-----------------|------------|--------------|---------------|------------------|-----------|
| Item 7: Enforce timeout_per_card | 654 | 970 | 155 | 0 | 1 | 1779 |
| Item 8: Move eval to post-run | 385 | 563 | 183 | 0 | 1 | 1131 |
| Item 9: EvalResult v2 schema | 751 | 331 | 130 | 0 | 1 | 1212 |
| Item 10: run_summary.json aggregation | 302 | 218 | 236 | 0 | 1 | 756 |
| Item 11: Allowlist contamination | 298 | 233 | 75 | 0 | 1 | 606 |
| Item 12: Fix test_utils.md imports | 66 | — | — | 0 | 0 | 66 |
| Item 13: Add GameState to template | 73 | — | — | 0 | 0 | 73 |
| Item 14: Simplify postmortem schema | 507 | 320 | 104 | 0 | 1 | 931 |
| Item 15: Pre-flight validation | 1389 | 312 | 82 | 0 | 1 | 1783 |
| Item 16: Smoke tests + MockAdapter | 690 | 1044 | 319 | 0 | 1 | 2053 |
| Dir summaries | 250 | — | — | — | — | 250 |
| Test audit | — | 2009 | — | — | — | 2009 |
