# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 7: Enforce timeout_per_card (fixes Issue #14)

### Tests
- `tests/test_timeout_enforcement.py` — Tests for hard timeout enforcement at strategy and adapter level

### Implementation
- `silverquillm/strategies.py` — Call adapter.kill() on timeout in both BlindStrategy and ImplTestStrategy
- `silverquillm/adapters/base.py` — Added kill() no-op to AgentAdapter; run_with_retries calls self.kill() before raising TimeoutError
- `silverquillm/adapters/opencode.py` — Track _process, start_new_session=True, kill via os.killpg process-group
- `silverquillm/adapters/aider.py` — Track _process, start_new_session=True, kill via os.killpg process-group
- `silverquillm/adapters/claude_code.py` — Track _process, start_new_session=True, kill via os.killpg process-group
- `silverquillm/adapters/pi.py` — Track _process, start_new_session=True, kill via os.killpg process-group