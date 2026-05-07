# Directory Summary — `tests/benchmark/`

## Purpose

Integration tests and shared test helpers for the full benchmark pipeline. Tests in this subpackage exercise the end-to-end flow (card loading → agent session → evaluation → result saving) using mock agent callables rather than real LLM agents.

## Key Files

| File | Lines | Responsibility |
|------|-------|---------------|
| `__init__.py` | — | Package init for benchmark test subpackage. |
| `test_helpers.py` | 182 | **Integration test utilities** — `mock_blind_callable()` and `mock_test_informed_callable()` factory functions that return mock agent callables; `make_benchmark_config()` factory for creating `BenchmarkConfig` instances with test defaults. |
| `test_e2e.py` | 247 | **E2E integration tests** — `TestFullPipeline` class with `test_full_pipeline_two_cards` (verifies complete run with result files) and `test_workspace_contamination_detected` (verifies violation detection halts execution). Marked with `@pytest.mark.integration`. |

## Testing Approach

- **Mock agents**: Tests use callable factories that simulate agent behavior (writing implementation files) without invoking real LLM APIs.
- **Temp directories**: All tests run in isolated temporary directories to avoid polluting the repo.
- **Integration marker**: E2E tests use `@pytest.mark.integration` for selective execution.
- **Config factory**: `make_benchmark_config()` provides sensible defaults that can be overridden per-test.
