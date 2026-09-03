Status: SETTLED

Last updated: 2026-09-03

# Testing Conventions

Testing conventions for **bench-authored tests** in the SilverquiLLM-bench repository — i.e. Platform tests, Audited tests, Engine tests, and FDN Reference Tests (everything maintainers write), but not Agent tests.

Scope: tests we write — host-side suites under `tests/`, FDN reference tests staged into the workspace at `benchmarks/sos/workspace/cards/fdn/{collector_number}/tests.py`, and audited SOS grader tests at `benchmarks/sos/data/tests/audited/sos/{collector_number}/tests.py`.

Out of scope: **Agent tests** inside the workspace (e.g., `engine_tests/test_*.py` authored during a run). The grader is the source of truth for scoring, not agent test hygiene, so we deliberately do not bind the agent to these rules and we do not stage this document into the workspace. The workspace `pytest.ini` carries the `timeout = 300` safety net regardless (see [WORKSPACE-CONTRACT.md](WORKSPACE-CONTRACT.md)).

These rules exist to prevent tests from hanging, killing processes, or otherwise disrupting the development environment.

## Motivation

PR #11 demonstrated a critical failure mode: a Tester subagent wrote `test_timeout_enforcement.py` containing `os.killpg()` calls against a `MagicMock` process. Because `int(MagicMock())` returns `1`, the test sent `SIGTERM` to process group 1, killing the entire container — including the agent that was implementing the next TODO item.

These conventions prevent that class of bug and others like it.

---

## Hard Safety Net: `pytest-timeout`

The repo uses `pytest-timeout` with a global default for the **host-side** suite in `pyproject.toml`:

```javascript
[tool.pytest.ini_options]
timeout = 300
```

Any single test that exceeds 300 seconds is killed automatically. This is the last line of defense — tests should be designed to complete well under this limit even when the code under test is broken. The **workspace** suite carries the same `timeout = 300` value in its own `benchmarks/*/workspace/pytest.ini` (pytest does not inherit config across rootdir boundaries — see [WORKSPACE-CONTRACT.md](WORKSPACE-CONTRACT.md)).

For tests that intentionally exercise slow paths, use a per-test marker:

```python
@pytest.mark.timeout(10)
def test_timeout_fires_within_budget():
    ...
```

---

## Rules

### 1. Never use real infinite loops or long sleeps in tests

**Bad:**

```python
class _SleepForeverAdapter:
    def run(self, prompt, workspace):
        while True:
            time.sleep(0.1)  # hangs if timeout code is broken
```

**Good:**

```python
class _BlockingAdapter:
    def __init__(self):
        self._stop = threading.Event()
    def run(self, prompt, workspace):
        self._stop.wait(timeout=60)  # blocks but is killable
    def kill(self):
        self._stop.set()
```

If a test needs to simulate a slow or hanging operation, use `threading.Event.wait()` with a generous but finite timeout, or mock `time.sleep` entirely.

### 2. Never let real OS signal/kill functions execute in tests

**Bad:**

```python
def test_kill_terminates_active_process(self):
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    adapter._process = mock_proc
    adapter.kill()  # calls real os.killpg() with int(MagicMock()) == 1 → kills PID group 1
```

**Good:**

```python
def test_kill_terminates_active_process(self):
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.pid = 99999  # explicit fake PID, not MagicMock auto-int
    adapter._process = mock_proc

    with patch("os.getpgid", return_value=99999), \
         patch("os.killpg") as mock_killpg:
        adapter.kill()

    mock_killpg.assert_called_once_with(99999, signal.SIGTERM)
```

Functions that must always be mocked or patched in tests:

- `os.kill()`, `os.killpg()`
- `signal.signal()`, `signal.alarm()`
- `subprocess.Popen()` (when testing kill/terminate logic)
- Any function that sends signals to process groups
### 3. Always set explicit values on mock attributes used as system identifiers

`MagicMock()` auto-creates attributes that return new `MagicMock` instances. When these are passed to system calls that coerce to `int`, `MagicMock.__int__()` returns `1` — which maps to PID 1 (init) on Linux.

**Bad:**

```python
mock_proc = MagicMock()
# mock_proc.pid is auto-MagicMock → int() returns 1 → PID 1
os.getpgid(mock_proc.pid)  # getpgid(1) → process group of init
```

**Good:**

```python
mock_proc = MagicMock()
mock_proc.pid = 99999  # explicit fake PID
mock_proc.returncode = 0
```

Always explicitly set `.pid`, `.returncode`, `.exitcode`, and any other attribute that might be passed to OS-level functions.

### 4. All tests must be self-terminating within 10 seconds

Even if the code under test is completely broken (infinite loop, deadlock, missing return), the test itself must finish. Do not rely on the code under test having correct timeout behavior — that's what you're testing.

Strategies:

- Mock the blocking operation entirely
- Use `threading.Event.wait(timeout=5)` instead of `while True`
- Use `@pytest.mark.timeout(10)` as a per-test safety net
- Use `signal.alarm()` as a test-level watchdog (not the same as the code under test's alarm)
### 5. Never call `game.run()` or enter the game loop in unit tests

The MTG game loop can run indefinitely if the `DeterministicPlayer` script is exhausted. Always test game logic step-by-step:

**Bad:**

```python
def test_spell_resolves():
    game = create_game(...)  
    game.run()  # may loop forever if player script ends early
```

**Good:**

```python
def test_spell_resolves():
    game = create_game(...)
    cast_spell(game, player, "Lightning Bolt", targets=[opponent])
    resolve_top(game)
    assert opponent.life == 17
```

Use `test_utils` helpers: `create_game()`, `set_board_state()`, `cast_spell()`, `resolve_top()`, `advance_to_phase()`. These advance game state deterministically without entering the open-ended game loop.

### 6. Never spawn real subprocesses in unit tests

Tests that need to verify subprocess behavior should mock `subprocess.Popen` or use `unittest.mock.patch`. Real subprocess spawning creates orphan processes, port conflicts, and environment-dependent failures.

**Exception:** Integration tests that verify the runner pipeline may use mock adapters, but must not spawn real LLM-calling processes or Docker containers.

### 7. Clean up all resources in test teardown

Use `tmp_path` (pytest fixture) for temporary files. Use context managers or `try/finally` for threads, events, and timers. Never leave background threads running after a test completes.

### 8. Invoke the CLI as a module in integration tests

Integration tests that spawn the CLI as a subprocess must use `[sys.executable, "-m", "silverquillm.cli", ...]`, never `["silverquillm", ...]`. This guarantees the test exercises the current worktree, not a potentially stale installed entry point.

**Bad:**

```python
subprocess.run(["silverquillm", "run", "--image", ...])
```

**Good:**

```python
import sys
subprocess.run([sys.executable, "-m", "silverquillm.cli", "run", "--image", ...])
```

---

## Checklist for Reference Test Authors

Before committing any bench-authored test file (host-side or staged reference), verify:

- [ ] No `while True` loops without a guaranteed exit condition
- [ ] No `time.sleep()` calls longer than 5 seconds
- [ ] No real `os.kill*()` or `signal.*()` calls — all patched
- [ ] All mock PIDs/process attributes set to explicit fake values (not auto-MagicMock)
- [ ] No `game.run()` or open-ended game loop calls
- [ ] No real `subprocess.Popen()` in unit tests — all mocked
- [ ] Test completes in under 10 seconds even if code under test is broken
- [ ] `tmp_path` used for all filesystem operations
- [ ] No background threads or timers left running after test
- [ ] Integration tests invoke CLI as `[sys.executable, "-m", "silverquillm.cli", ...]`
---

## Enforcing These Conventions

1. **`pytest-timeout = 300s`** — global hard limit for the host-side suite in `pyproject.toml`
2. **CI gate** — `pytest` runs on every PR; any timeout or hang fails the build
3. **Author scope** — These rules govern bench-authored tests only. Agent tests inside the workspace are not bound by this doc and are not graded; only the Audited tests (host-side grader) determine the score. The workspace `pytest.ini` `timeout = 300` setting is the only safety net that follows tests into the container.
