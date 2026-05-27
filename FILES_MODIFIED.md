# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Bootstrap Test Oracle Workspace + validation harness

### Tests
- `tests/test_oracle_workspace_bootstrap.py` — verifies workspace structure, stubs, helpers, harness, and stub detection logic

### Implementation
- `benchmarks/sos/data/test_oracle_workspace/` — new directory mirroring workspace/ with engine, cards/fdn, cards/stubs, cards/sos (10 audited stubs), engine_tests, AGENTS.md, pytest.ini
- `benchmarks/sos/data/test_oracle_workspace/test_utils.py` — extended test helpers; resolve_top resolves one item, _resolve_top_of_stack drains full stack, assert_casting_error checks exc.__cause__ type
- `tests/test_audited_against_reference.py` — validation harness with AST-based _is_stub_impl that detects non-dunder methods as real implementations


## Item 2: sos_1 — The Dawning Archaic oracle impl

### Tests
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_1/tests.py` — 20 tests covering identity, cost reduction, attack trigger (decline/accept), exile replacement, scope, targeting
- `benchmarks/sos/data/tests/audited/sos/sos_1/tests.py` — mirror tests (depend on stubs from TODO item 6)

### Implementation
- `benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_1/card_impl.py` — Full oracle: Legendary Creature with cost_reduction, attack trigger with target lock-in, one-shot exile replacement effect
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/conftest.py` — Synthetic card_impl module for workspace test imports
- `benchmarks/sos/data/test_oracle_workspace/test_utils.py` — _set_zone registers triggers/replacement effects on battlefield, clears summoning sickness
- `benchmarks/sos/data/test_oracle_workspace/engine/combat.py` — declare_attackers_step fires AttacksTriggeredEvent for each attacker
- `benchmarks/sos/data/test_oracle_workspace/engine/casting.py` — _resolve_spell consults replacement effects before moving spells to graveyard; added _SpellToGraveyardReplacementEvent


## Item 3: sos_4 — Together as One oracle impl

### Tests
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_4/tests.py` — 11 rewritten tests: identity, 1-color resolution, 5-color resolution, 0-color discriminator, fizzle-keeps-legal-effects

### Implementation
- `benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_4/card_impl.py` — Full oracle: Sorcery with Converge, TargetRequirement with filter_fn, multi-target partial resolution, all-illegal-counters logic
- `benchmarks/sos/data/test_oracle_workspace/engine/game.py` — Extended deal_damage() to handle planeswalker targets (remove loyalty counters)
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_4/__init__.py` — Package init for test discovery
- `benchmarks/sos/data/tests/audited/sos/sos_4/tests.py` — Copy of rewritten tests to final audited location
