# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Test failure: Item 1 — _make_run_name() separator
- **Failing tests**: TestRunName assertions expect underscore separator
- **Tester's intent**: Test the new _make_run_name() function contract
- **Implementer's approach**: Used underscore to match tests, but TODO spec says hyphen
- **Coordinator decision**: fix tests — the TODO spec explicitly requires hyphen separator (`<set_code>-<timestamp>`)
- **Reasoning**: The TODO spec is unambiguous: format is `f"{set_code}-{ts}"` with example `sos-2026-05-16T19-49`. Tests were written with wrong assumption.
