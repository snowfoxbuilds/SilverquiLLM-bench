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

## Item 3: Card complexity classifier

### Tests
- `tests/test_card_classifier.py` — 24 tests covering tier classification, SOS integration, edge cases

### Implementation
- `benchmark/card_classifier.py` — Heuristic-based card complexity classifier with targeting floor fix (target → at least medium)
- `benchmarks/sos/data/sos_classified.json` — Regenerated classification output for all 368 SOS cards with fixed targeting heuristic

## Item 4: Card spec generator

### Tests
- (no test files provided by tester)

### Implementation
- `benchmark/card_spec.py` — Card spec generator with generate_card_spec() and generate_all_specs() functions
- `benchmarks/sos/cards/*/card_spec.json` — Generated 368 per-card JSON spec files for SOS set

## Item 5: Template generator

### Tests
- `tests/test_template_gen.py` — 49 tests covering class name conversion, base class resolution, template compilation/exec

### Implementation
- `benchmark/template_gen.py` — Template generator with PascalCase word-boundary fix and ambiguous multi-type fallback to CardImpl

