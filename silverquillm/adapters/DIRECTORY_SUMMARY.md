# Directory Summary — `silverquillm/adapters/`

## Purpose

Pluggable agent adapter system for the benchmark runner. Provides an abstract base class (`AgentAdapter`) and a registry-based factory (`get_adapter`) for instantiating concrete adapters by name. Each adapter wraps an external LLM coding tool CLI (OpenCode, Claude Code, Aider, Pi) as a subprocess.

## Key Files

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package init — re-exports `AgentAdapter`, `get_adapter`, `register_adapter`. Imports all concrete adapter modules to trigger auto-registration. |
| `base.py` | **Abstract base class** — `AgentAdapter` ABC with abstract `run()`, `setup()`, `teardown()` methods. `run_with_retries()` helper for retry logic. `_ADAPTER_REGISTRY` dict, `register_adapter()` decorator, `get_adapter(config)` factory that reads `config.agent.adapter`. |
| `opencode.py` | **OpenCode adapter** — Wraps `opencode` CLI via subprocess. Passes prompt via stdin. Removes invalid `--thinking` flag. Auto-registers as `"opencode"`. |
| `claude_code.py` | **Claude Code adapter** — Wraps `claude` CLI with `--print` flag. Passes prompt via stdin. Auto-registers as `"claude_code"`. |
| `aider.py` | **Aider adapter** — Wraps `aider` CLI with `--message-file` for prompt delivery and `--no-auto-commits`. Auto-registers as `"aider"`. |
| `pi.py` | **Pi adapter** — Wraps `pi` CLI with `--no-interactive` flag. Passes prompt via stdin. Auto-registers as `"pi"`. |

## Important Classes / Functions

- **`AgentAdapter`** — ABC. `__init__(config)` stores `BenchmarkConfig`. Subclasses implement `setup()`, `run(prompt, workspace) -> str`, `teardown()`.
- **`run_with_retries(prompt, workspace, max_retries, delay)`** — Built-in retry logic on the base class.
- **`register_adapter(name)`** — Class decorator that registers an adapter class in `_ADAPTER_REGISTRY`.
- **`get_adapter(config)`** — Factory: looks up `config.agent.adapter` in registry, instantiates, returns.

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

- `tests/test_adapter_base.py` — Base class, registry, factory, retry logic.
- `tests/test_opencode_adapter.py` — OpenCode adapter subprocess behavior.
- `tests/test_claude_code_adapter.py` — Claude Code adapter.
- `tests/test_aider_adapter.py` — Aider adapter.
- `tests/test_pi_adapter.py` — Pi adapter.
- `tests/test_agent_session_adapter.py` — Integration of adapters with AgentSession.
