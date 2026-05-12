# Directory Summary — `silverquillm/adapters/`

## Purpose

Pluggable agent adapter system for the benchmark runner. Provides an abstract base class (`AgentAdapter`) and a registry-based factory (`get_adapter`) for instantiating concrete adapters by name. Each adapter wraps an external LLM coding tool CLI (OpenCode, Claude Code, Aider, Pi) as a subprocess.

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package init — re-exports `AgentAdapter`, `get_adapter`, `register_adapter`. Imports all concrete adapter modules (including mock) to trigger auto-registration. |
| `base.py` | **Abstract base class** — `AgentAdapter` ABC with abstract `run()`, `setup()`, `teardown()` methods. `kill()` no-op method (overridden by concrete adapters for hard timeout enforcement). `run_with_retries()` helper with retry logic — calls `self.kill()` before raising `TimeoutError`. `_ADAPTER_REGISTRY` dict, `register_adapter()` decorator, `get_adapter(config)` factory that reads `config.agent.adapter`. |
| `opencode.py` | **OpenCode adapter** — Wraps `opencode` CLI via subprocess. Passes prompt via stdin. Removes invalid `--thinking` flag. Tracks `_process` with `start_new_session=True`; `kill()` via `os.killpg` process-group. Auto-registers as `"opencode"`. |
| `claude_code.py` | **Claude Code adapter** — Wraps `claude` CLI with `--print` flag. Passes prompt via stdin. Tracks `_process` with `start_new_session=True`; `kill()` via `os.killpg` process-group. Auto-registers as `"claude_code"`. |
| `aider.py` | **Aider adapter** — Wraps `aider` CLI with `--message-file` for prompt delivery and `--no-auto-commits`. Tracks `_process` with `start_new_session=True`; `kill()` via `os.killpg` process-group. Auto-registers as `"aider"`. |
| `pi.py` | **Pi adapter** — Wraps `pi` CLI with `--no-interactive` flag. Passes prompt via stdin. Tracks `_process` with `start_new_session=True`; `kill()` via `os.killpg` process-group. Auto-registers as `"pi"`. |
| `mock.py` | **Mock adapter** — `MockAdapter` with configurable behaviors for deterministic testing. Derives `card_name` from workspace `card_spec.json` for registry compatibility. `no_output` mode cleans seeded files. Used by `--dry-run` for environment validation. Auto-registers as `"mock"`. |

## Important Classes / Functions

- **`AgentAdapter`** — ABC. `__init__(config)` stores `BenchmarkConfig`. Subclasses implement `setup()`, `run(prompt, workspace) -> str`, `teardown()`, and optionally `kill()`.
- **`run_with_retries(prompt, workspace, max_retries, delay)`** — Built-in retry logic on the base class. Calls `self.kill()` before raising `TimeoutError`.
- **`kill()`** — No-op on base class; concrete adapters override to terminate subprocess via `os.killpg` process-group.
- **`register_adapter(name)`** — Class decorator that registers an adapter class in `_ADAPTER_REGISTRY`.
- **`get_adapter(config)`** — Factory: looks up `config.agent.adapter` in registry, instantiates, returns.
- **`MockAdapter`** — Deterministic test adapter with configurable behaviors; no external CLI dependency.

## Adapter Registration Pattern

```python
@register_adapter("my_tool")
class MyToolAdapter(AgentAdapter):
    def setup(self): ...
    def run(self, prompt, workspace): ...
    def teardown(self): ...
```

The `__init__.py` imports each concrete module so `@register_adapter` runs at import time.

## Dependencies

- **`silverquillm/config.py`** — `BenchmarkConfig` (passed to adapter constructor).
- **External CLIs** — Each adapter shells out to its respective CLI tool (`opencode`, `claude`, `aider`, `pi`).

## Testing

- `tests/test_adapter_base.py` — Base class, registry, factory, retry logic, kill() behavior.
- `tests/test_opencode_adapter.py` — OpenCode adapter subprocess behavior.
- `tests/test_claude_code_adapter.py` — Claude Code adapter.
- `tests/test_aider_adapter.py` — Aider adapter.
- `tests/test_pi_adapter.py` — Pi adapter.
- `tests/test_agent_session_adapter.py` — Integration of adapters with AgentSession.
- `tests/test_timeout_enforcement.py` — Hard timeout enforcement at strategy and adapter level.
- `tests/test_harness.py` — End-to-end smoke tests using MockAdapter.
