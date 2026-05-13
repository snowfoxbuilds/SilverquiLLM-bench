# Item 10: Fix test_timeout_enforcement.py — Rationale

## Problem
The `_BlockingAdapter` and `_BlockingNoKillAdapter` test helpers were plain classes, not `AgentAdapter` subclasses. After Item 6 changed strategies to call `adapter.run_with_retries()` instead of using `ThreadPoolExecutor`, these helpers lacked the `run_with_retries` method inherited from `AgentAdapter`, causing 9 test failures.

## Solution
Converted both helper classes to proper `AgentAdapter` subclasses:
- Added `super().__init__(config)` calls with optional config parameter (defaults to `_make_config(timeout=2)`)
- Added required abstract method stubs: `setup()`, `teardown()`
- `_BlockingNoKillAdapter` now inherits the base no-op `kill()` instead of having no kill method at all (functionally equivalent for timeout testing — the Event won't be released, so the threading timeout still fires)

## Design Decisions
- Used `config: BenchmarkConfig | None = None` with a default to avoid changing all 9+ test call sites that construct these adapters without arguments
- Kept the `threading.Event.wait(timeout=60)` pattern that was already correct per TESTING-CONVENTIONS.md
- No changes needed to adapter implementation files — the test file already had proper `os.getpgid`/`os.killpg` patching and `pid=99999` conventions

## Conventions
- Test helper adapters that need strategy-level testing must subclass `AgentAdapter` to get `run_with_retries()`
