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
