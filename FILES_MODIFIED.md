# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Fix Phase 1 tech debt

### Implementation
- `pyproject.toml` — Set requires-python to >=3.12, mypy python_version to 3.12, removed tomli conditional dep
- `ruff.toml` — Set target-version to py312
- `cards/foundations/simple_spells.py` — Removed 7 backward-compat aliases (LightningBolt, LavaAxe, etc.)
- `engine/turn.py` — Added import warnings and warnings.warn() in cleanup discard fallback
- `KEY_DECISIONS.md` — Updated decision #2 to reflect Python 3.12 target
- `tests/test_scaffold.py` — Updated scaffold tests to expect 3.12/py312 instead of 3.10/py311

