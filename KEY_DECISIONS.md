# Key Decisions

Persistent across runs. Records architectural decisions, conventions, and long-lived constraints.


## Package renamed from benchmark/ to silverquillm/
- **Context**: TODO item 1 required renaming the package directory.
- **Decision**: Package is now `silverquillm`. All imports use `from silverquillm.xxx import ...`. CLI entry point command name stays `benchmark`.
- **Reasoning**: The CLI command name is user-facing and doesn't need to match the internal package name. `tests/benchmark/` subdirectory was left as-is since it's a test helper directory, not the package being renamed.
- **Impact**: All source and test files updated. `_PROTECTED_DIRS` in `agent_session.py` now references `silverquillm`.

## Nested AgentConfig convention
- **Context**: Config was flat; needed nested `agent:` block per spec.
- **Decision**: Agent-related config lives under `agent:` in YAML and `config.agent.*` in code. Legacy flat access (`config.max_test_rounds`, `config.agent_tool`) works via deprecated properties. Field `agent_tool` renamed to `agent.adapter`.
- **Reasoning**: Backward-compatible properties allow gradual migration of consumers in the next TODO item.
- **Impact**: `silverquillm/config.py`, `config.example.yaml`, `silverquillm/results.py`.
