# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Spec deviation: Item 3 — Generate FDN card specs and templates
- **TODO spec expected**: Generate FDN card specs via new script.
- **Actual codebase state**: `scripts/generate_fdn_specs.py` and `cards/fdn/` (286 subdirs) already exist from commit 2dd3fbf.
- **What was implemented instead**: Nothing — item already complete. Verified: all specs valid, all tests pass.
- **Impact**: No files changed. Marked as complete.

## Disagreement: Item 5 — Fix container timeout
- **Reviewer comment (strict)**: Implementation must use `Popen` + `wait(timeout)`, not `subprocess.run(timeout=...)`.
- **Implementer justification**: Tests patch `subprocess.run` and cannot be modified; switching to Popen would break them.
- **Coordinator decision**: accept reviewer — the TODO explicitly requires Popen for a specific reason (subprocess.run kills the local CLI process before docker stop can run). The tests were also flagged by the reviewer as wrong (patching subprocess.run instead of Popen). Both must be updated.
- **Reasoning**: The whole point of this TODO is to fix a real bug where subprocess.run's timeout mechanism doesn't actually stop the container. The Tester will rewrite tests to mock Popen, then the Implementer will switch to Popen.
- **Impact**: `silverquillm/cli.py`, `tests/test_container_timeout.py`
