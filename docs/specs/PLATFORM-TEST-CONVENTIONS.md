Status: SETTLED

Last updated: 2026-10-03

# Platform Test Conventions

How maintainers write Platform Tests, the suites under the repository's top-level `tests/`, so they stay safe to run and cheap enough to run on every pull request.

## Context

Platform Tests verify the benchmark software, not agent output, and CI runs all of them on every pull request on a host it shares with other work.
Most of the suite's time went to the same Simulated Benchmarks and Workspace copies rebuilt for test after test, often to check one field each (grilling 2026-10-03).
Audited Tests and Reference Tests follow their own conventions; nothing here binds them.

## Design

### Safety

A Platform Test must never hang the suite, signal a real process, or reach real infrastructure:

- No open-ended loop or sleep: wait on an event with a finite timeout, and finish within the suite's per-test `pytest-timeout` even when the code under test is broken.
- No real `os.kill`, `os.killpg` or `signal` call reaches the OS, and a mocked process carries explicit fake identifiers (`pid`, `returncode`), never an auto-generated `MagicMock`.
- A unit test spawns no real subprocess for the behavior it checks; it patches `subprocess`.
- An integration test that runs the CLI runs it as `[sys.executable, "-m", "silverquillm.cli", ...]`, so it exercises this worktree, never a stale installed entry point.
- Grading reaches no Docker daemon: a unit test that grades injects `tests.grader_fixtures.local_grader()`, which interprets the Grader Container's exact arguments without Docker, and the suite's conftest fails any unit test that reaches the grader's Docker client.
  A test that needs a real daemon or image carries the `integration` marker, which the default run deselects.
- Threads, timers and temporary files are cleaned up when the test ends; files live under `tmp_path`.

### What counts as expensive

Three operations cost seconds each and dominate the suite's time (grilling 2026-10-03):

| Operation | Example |
| --- | --- |
| A Simulated Benchmark | `run_benchmark`, a recovery or a re-grade on the toy benchmark, with `FixtureHost` and the local grader stand-in |
| A grading | `evaluate_run` or an audited-suite run, which starts pytest in a subprocess |
| A whole-tree copy | Staging a Workspace, or copying a benchmark, Known-Best or run tree |

Everything else, such as building a record, scoring an evaluation or validating a manifest, is cheap.

### End-to-end tests and spot checks

A Simulated Benchmark is an end-to-end test (grilling 2026-10-03):

- It runs only for a genuinely distinct pipeline configuration: a successful run, a failing grader, a killed run and its recovery, a re-grade, Combined Regression, results sharing.
- It asserts everything its configuration decides, rather than one field per run.
- Two runs that differ only in which field a test reads are one run.

A spot check never runs a Simulated Benchmark (grilling 2026-10-03):

- It calls the unit it checks directly, building its inputs with a small helper (a record, an evaluation, a host result, benchmark data) and stubbing the collaborators it does not check (the host, the grader, the evaluator).
- A rule about a record's fields validates a copy of an existing record; a rule about scores calls the score mapping on a constructed evaluation.

### Sharing expensive results

An expensive result is built once and shared (grilling 2026-10-03):

| A test that | Uses |
| --- | --- |
| Only reads the result | A module- or session-scoped fixture, such as the session's `plain_run` (one successful Simulated Benchmark) or `staged_sos_workspace` (the staged SOS Workspace) |
| Changes the result | A module-scoped template cloned into the test's own `tmp_path` (`tests/retained_runs.py`); the clone rewrites the template's root in every text file, because records, login journals and plugin environments name their files by absolute path |

A test that reads a shared result never writes to it; a test that writes takes a clone.
A module- or session-scoped fixture is built outside the suite's autouse fixtures, so it applies the unit-test environment itself (`retained_runs.building()`): no grader Docker, and a clean run provenance.

### One assertion, one place

Before adding a test, find where its behavior is already asserted, and extend that test rather than paying for the same setup again (grilling 2026-10-03).
A test that becomes a strict subset of another is deleted.

### Parallel workers and the temp budget

Platform Tests may run in parallel worker processes:

- A shared fixture is built once per worker process.
- A test writes only inside its own `tmp_path` or a fixture's directory, and restores any working directory or environment variable it changes.
- A passing test's `tmp_path` is removed when it finishes, and a passing session that leaves more than the budget in `tests/temp_budget.py` behind fails; shared fixtures stay small enough to fit well under it.

### Checklist

Before committing a Platform Test, verify:

- [ ] It finishes within the per-test timeout even when the code under test is broken
- [ ] No real signal, kill or unmocked subprocess reaches the OS in a unit test
- [ ] Grading goes through `local_grader()`; Docker-backed tests are marked `integration`
- [ ] A Simulated Benchmark appears only in an end-to-end test of a distinct configuration, asserting everything that configuration decides
- [ ] A spot check builds or stubs its inputs instead of running the pipeline
- [ ] Expensive results come from a shared fixture, cloned before the test changes them
- [ ] The behavior is not already asserted by another test

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-013](../adr/ADR-013-grading-runs-in-a-network-less-grader-container.md) | Grading runs in a network-less Grader Container, which unit tests replace with the local stand-in |
