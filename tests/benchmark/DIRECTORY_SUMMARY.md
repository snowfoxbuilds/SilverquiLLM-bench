# Directory Summary — `tests/benchmark/`

## Purpose

Integration tests and helpers for full benchmark pipeline end-to-end testing. Tests verify the complete flow from config loading through agent session to result recording.

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package init. |
| `test_helpers.py` | **Integration test helpers** — Mock agent callables (blind + test-informed) and `BenchmarkConfig` factory using nested `AgentConfig`. |
| `test_e2e.py` | **E2E integration tests** — `test_full_pipeline_two_cards` and `test_workspace_contamination_detected`. Uses `config.agent.adapter` for adapter selection. |

## Dependencies

- `silverquillm/` — All runner modules under test.
- `silverquillm/config.py` — `BenchmarkConfig`, `AgentConfig`.
- `tests/test_utils.py` — Shared test helpers.
