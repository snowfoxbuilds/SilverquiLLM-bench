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

## Deprecated flat config properties removed
- **Context**: After migrating all consumers, backward-compat properties were no longer needed.
- **Decision**: Removed deprecated properties from BenchmarkConfig. All code uses `config.agent.*`. YAML backward compat for flat keys is preserved in `load_config()`.
- **Reasoning**: Clean API surface; no more dual access patterns.
- **Impact**: All test fixtures use `agent=AgentConfig(...)`. New code must use `config.agent.*`.

## AgentAdapter pattern
- **Context**: Need pluggable agent adapters for different CLI tools.
- **Decision**: ABC with `run(prompt, workspace) -> str`, `setup()`, `teardown()`. Registry-based factory via `get_adapter(config)`. Concrete adapters call `register_adapter("name", cls)` at module level. `run_with_retries` uses a single overall deadline from `timeout_per_card`.
- **Reasoning**: Registry pattern allows adapter modules to self-register on import. Overall deadline prevents retry multiplication of timeouts.
- **Impact**: `silverquillm/adapters/base.py`, `silverquillm/adapters/__init__.py`.

## 6. Canonical tier key is `complexity_tier`
- **Context**: Codebase used both `tier` and `complexity_tier` inconsistently across classifier, scorer, evaluator, card specs, and JSON data files.
- **Decision**: Standardized on `complexity_tier` as the canonical key. All readers accept both keys with `complexity_tier` preferred. All writers emit `complexity_tier` (JSON data files emit both for backward compat).
- **Reasoning**: `complexity_tier` is more descriptive and self-documenting. Adding backward-compat fallback ensures older JSON files still work.
- **Impact**: `card_classifier.py`, `card_spec.py`, `cli.py`, `prototype.py`, `results.py`, `run_utils.py`, `sos_classified.json`, `prototype_cards.json`.
