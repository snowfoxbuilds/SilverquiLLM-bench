# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Spec deviation: Item 8 — PiAdapter CLI interface
- **Reviewer comment**: The initial implementation used invalid `--no-interactive` and `--model` flags that don't exist in the upstream `pi` CLI.
- **Coordinator decision**: Fix the adapter to use a minimal, conservative approach — pass prompt as a positional argument since `pi` accepts natural-language queries as argv. Avoid inventing flags. Keep the adapter thin and easy to adjust once the real `pi` CLI docs are verified.
- **Reasoning**: We don't have verified `pi` CLI documentation. A conservative positional-argument approach is safest.
- **Impact**: `silverquillm/adapters/pi.py`, `tests/test_pi_adapter.py`

## Spec deviation: Item 10 — timing field name
- **TODO spec expected**: `timing` field in postmortem JSONL
- **Actual implementation**: `timing_ms` field
- **Coordinator decision**: Accept `timing_ms` — it's self-documenting about the unit (milliseconds).
- **Reasoning**: `timing` is ambiguous (seconds? ms?). `timing_ms` is clearer for downstream consumers.
- **Impact**: `silverquillm/agent_session.py`, `tests/test_postmortem_logging.py`
