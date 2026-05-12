# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.

## Item 7 — Reviewer required process-group termination
- **Context**: Initial implementation only added a termination method to OpenCode adapter and didn't use process-group signals. Reviewer flagged that all adapters need termination and must use `os.killpg` for hard timeout.
- **Decision**: Revised to add process-group termination with `start_new_session=True` + `os.killpg()` to all four adapters, and `run_with_retries()` now calls `self.kill()` before raising TimeoutError.
- **Reasoning**: Soft timeouts that don't actually terminate subprocesses defeat the purpose of `timeout_per_card`.
- **Impact**: All adapter files, base.py, strategies.py, test_timeout_enforcement.py.

## Item 8 — Reviewer caught schema and audited-lookup issues
- **Context**: Initial post_eval.py used nondeterministic audited test scanning (first match across set dirs) and introduced a new flat result.json schema that would break existing consumers.
- **Decision**: Revised to use deterministic `{set_code}/{collector}` lookup from card metadata and preserved existing result.json schema format. V2 schema is deferred to item 9.
- **Reasoning**: Multiple benchmark sets can share collector numbers; schema changes must be coordinated with all consumers.
- **Impact**: silverquillm/post_eval.py, tests/test_post_eval.py.

## Item 9 — Reviewer caught v2 not wired in and mode-unaware scoring
- **Context**: Initial v2 implementation added the schema but didn't wire it into harness (cli.py/post_eval.py still used v1), scorer ignored mode when converting v2→v1 columns, and v1→v2 normalization left nested implementation.
- **Decision**: Wired save_card_result_v2 into cli.py and post_eval.py, made scorer mode-aware (blind→Cat1 only, impl_test→Cat2 only), and flattened v1 implementation in normalizer.
- **Reasoning**: The whole point of v2 is to replace v1 in practice, not just exist as dead code. Mode-aware scoring preserves the blind/tested distinction.
- **Impact**: silverquillm/cli.py, silverquillm/post_eval.py, silverquillm/results.py, silverquillm/scorer.py.

## Item 10 — Reviewer caught non-deterministic timestamp and legacy compat gaps
- **Context**: aggregate_run() used datetime.now() breaking idempotency, token extraction only handled dict shape, and legacy status strings weren't normalized.
- **Decision**: Derived timestamp from latest result.json mtime, handled both int/dict token shapes, normalized "ok"/"success" → "completed".
- **Reasoning**: Aggregation must be a pure function for `benchmark aggregate` re-runs; backward compat with existing run artifacts is required.
- **Impact**: silverquillm/aggregator.py, tests/test_aggregator.py.

## Item 11 — Reviewer caught incomplete allowlist scope
- **Context**: Initial implementation still only snapshotted _PROTECTED_DIRS, leaving writes to scripts/, data/, repo root undetected.
- **Decision**: Expanded snapshot to walk entire repo tree for true allowlist semantics. Fixed flaky mtime test by using explicit os.utime() bumps.
- **Reasoning**: Allowlist means "deny by default" — must snapshot everything to detect any unauthorized change.
- **Impact**: silverquillm/agent_session.py, tests/test_allowlist_contamination.py.

## Reviewer intervention: Item 14 — Simplify postmortem schema
- **Reviewer comment (strict #1)**: Event helpers `file_written`, `eval_result`, `regression_check` defined but never called from production code — real runs would never produce these events.
- **Reviewer comment (strict #2)**: Tests only call helpers directly, missing integration coverage for actual call sites.
- **Coordinator decision**: Accept both. Implementer wired helpers into harvest_results(), post_eval, and CLI regression loop. Tester added 11 integration tests.
- **Reasoning**: Helpers without call sites are dead code; the TODO clearly requires production use. Integration tests ensure wiring stays intact.
- **Impact**: agent_session.py, post_eval.py, cli.py, tests/test_postmortem_schema_v2.py

## Reviewer intervention: Item 15 — Pre-flight validation at run start
- **Reviewer comments (4 strict)**: Missing engine test suite check, test_utils only checks file existence not actual import, workspace validates run_dir not .workspace/, tests don't cover these gaps.
- **Coordinator decision**: Accept all. Implementer added engine pytest subprocess, actual import verification, and .workspace/ validation. Tester added 9 integration tests.
- **Reasoning**: All checks were explicitly required by the TODO text. File-existence-only checks defeat the purpose of preflight validation.
- **Impact**: silverquillm/preflight.py, tests/test_preflight.py

## Spec deviation: 15 Item Engine test scope 
- **TODO spec expected**: `pytest tests/ -x -q --ignore=tests/audited`
- **Actual implementation**: `pytest tests/engine/ -x -q`
- **What was implemented instead**: Scoped to `tests/engine/` because the TODO says "Engine test suite" and running all tests would include unrelated harness tests.
- **Impact**: silverquillm/preflight.py

## Reviewer intervention: Item 16 — Smoke tests with mock adapter
- **Reviewer comments (6 strict)**: MockAdapter not wired through registry, no_output doesn't clean seeded files, tests not truly e2e (bypass AgentSession), violation tests skip _check_violations, aggregation is unit test not pipeline test, dry-run only checks imports.
- **Coordinator decision**: Accept all. Implementer fixed MockAdapter (registry wiring + no_output cleanup). Tester rewrote all 27 tests to use AgentSession.run_card() and CliRunner for true e2e coverage.
- **Reasoning**: Smoke tests that bypass the harness layers defeat the purpose — they wouldn't catch real integration regressions.
- **Impact**: silverquillm/adapters/mock.py, tests/test_harness.py, silverquillm/cli.py
