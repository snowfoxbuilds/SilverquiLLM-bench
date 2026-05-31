# Run Stats

**Skill**: execute-todo-with-subagents
**Started**: 2026-05-31T01:52:55Z
**Finished**: 2026-05-31T03:50:22Z
**Total duration**: 1h 57m 27s
**Total duration (seconds)**: 7047

## Summary
- TODO items completed: 9
- Items requiring test dispute: 0
- Items requiring review revision: 1 (Item 2 — 2 strict Reviewer comments → 1 Implementer revision)
- Items with coordinator arbitration: 2 (Item 2 review arbitration; Item 5 scope-violation arbitration + directed revert)
- Commits: 11 (1 reset + 9 item commits + RUN_STATS)
- RUN_DECISIONS entries: 3 (Item 2 spec deviation; Item 5 arbitration; Item 9 config.json supporting addition)
- KEY_DECISIONS entries added: 1 (Phase 19 per-card `result.json` schema: `tests_hash` + `test_nodes`)
- Directories resummarized (aggregated across items): 22
- Coverage tests added (aggregated across items): 90
- Test suite result: passing (272 Phase 19 + evaluator tests pass via `python3 -m pytest` over all 11 new/changed test files + `test_evaluator.py`)

## Tokens (subagents)
- Total Implementer tokens: 329375 (includes 2 revision rounds: Item 2 = 18014, Item 5 = 35164)
- Total Tester tokens: 329142
- Total Reviewer tokens: 326669
- Total DirectorySummarizer tokens: 211797
- Total TestCoverageImprover tokens: 299730
- Total across all subagents: 1496713
- Coordinator tokens: null (not self-observable)

## Per-item breakdown
| TODO item | Implementer | Tester | Reviewer | DirSumm | TestCov | Test disputes | Review revisions | Duration (s) |
|-----------|-------------|--------|----------|---------|---------|---------------|------------------|--------------|
| 1. Stamp tests_hash into result.json         | 18131 | 48021 | 21891 | 16250 | 35585 | 0 | 0  | 419 |
| 2. Per-test-node pass/fail outcomes          | 53006 | 50960 | 37016 | 21153 | 47559 | 0 | 1  | 834 |
| 3. Scaffold harvest_validated_results.py     | 23020 | 24301 | 35891 | 27444 | 25365 | 0 | 0  | 483 |
| 4. Emit long-format harvested_results.jsonl  | 28842 | 29895 | 29434 | 24452 | 34301 | 0 | 0  | 508 |
| 5. Back-compat legacy harvest                | 75251 | 39237 | 34392 | 24462 | 38430 | 0 | 1* | 779 |
| 6. Cross-impl breadth summary (--summary)    | 32049 | 45722 | 26048 | 15491 | 33880 | 0 | 0  | 460 |
| 7. test-investigation SKILL.md               | 27454 | 21753 | 38910 | 21049 | 15655 | 0 | 0  | 380 |
| 8. Discovery-candidate miner                 | 33909 | 34677 | 40333 | 32720 | 32916 | 0 | 0  | 652 |
| 9. Promotion-bar gate                        | 37713 | 34576 | 62754 | 28776 | 36039 | 0 | 0  | 693 |

\* Item 5's revision was coordinator-initiated (the Implementer changed an established public API and edited a Tester-owned test file) and reverted via directives — not triggered by a Reviewer strict finding. The Item 5 Implementer token figure includes both the initial (40087) and the revert (35164) rounds.

Notes:
- Token figures are `subagent_tokens` reported on each agent return.
- Per-item "Duration (s)" is the sum of that item's subagent wall-times (including revision rounds) and excludes coordinator orchestration time; the additive subagent time across all items is ~86.8 min, less than the ~117 min end-to-end wall clock.
