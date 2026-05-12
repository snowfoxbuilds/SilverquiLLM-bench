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
