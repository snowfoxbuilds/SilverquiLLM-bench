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

## Item 2: Benchmark package scaffold + SOS data fetch

### Tests
- (no test files provided by tester)

### Implementation
- `benchmark/__init__.py` — Created benchmark runner package with docstring
- `benchmarks/__init__.py` — Created benchmarks namespace package
- `benchmarks/sos/__init__.py` — Created SOS benchmark set package
- `benchmarks/sos/fetch_data.py` — SOS data fetcher with normalization, stats logging, and CLI
- `benchmarks/sos/data/sos.json` — Cached normalized SOS card data (368 cards from Scryfall)
- `benchmarks/sos/cards/.gitkeep` — Placeholder for SOS card implementations
- `benchmarks/sos/results/.gitkeep` — Placeholder for SOS benchmark results
- `pyproject.toml` — Added pyyaml and click deps; included benchmark* and benchmarks* in package discovery

