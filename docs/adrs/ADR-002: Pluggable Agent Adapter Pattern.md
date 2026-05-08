Status: ACCEPTED

Date: 2026-05-08

## Context

The benchmark needs to evaluate multiple LLM coding agents (OpenCode, Claude Code, Aider, Pi). Each agent tool has a different CLI interface, different tool-calling capabilities, and different output formats. The runner needs to drive all of them through the same benchmark flow.

## Decision

Introduce an abstract `AgentAdapter` base class that each agent tool implements. The runner interacts only with the adapter interface — it never knows which underlying tool is running.

```python
class AgentAdapter(ABC):
    @abstractmethod
    def run(self, prompt: str, workspace: Path, timeout: int) -> AgentRunResult: ...
    @abstractmethod
    def get_session_log(self) -> str: ...
```

Adapter selected by `agent.adapter` in the run config. Each adapter handles its own CLI invocation, output parsing, and contamination enforcement.

## Trade-offs

**Gains:**

- Adding a new agent tool requires only implementing one class — no runner changes
- Each adapter can handle tool-specific quirks (e.g., Aider's text-based edits vs OpenCode's function calling)
- Contamination controls can be adapter-specific (e.g., OpenCode `deny` permissions vs Aider `--no-browser`)
- Postmortem log format is standardized regardless of underlying tool
**Costs:**

- Abstraction overhead — adapter must translate between runner expectations and tool realities
- Lowest-common-denominator risk — features available in one tool (e.g., tool-calling) can't be assumed
- Testing burden — each adapter needs its own integration tests
## Alternatives Considered

- **Hardcode one tool (OpenCode)**: Simpler, but locks the benchmark to one agent ecosystem and can't compare agent tools
- **Plugin system with dynamic loading**: More flexible but over-engineered for 4 adapters
- **Subprocess-only with config-driven CLI templates**: Less code but can't handle tool-specific output parsing or state management
## Consequences

- v1 ships with four adapters: `opencode`, `claude_code`, `aider`, `pi`
- Rules access is equalized (greppable file, not tool-calling) to avoid adapter-specific advantages
- Each adapter captures stdout/stderr and structures it into the postmortem log
- `_run_opencode` naming in `agent_session.py` is a legacy artifact — to be renamed `_run_agent`
