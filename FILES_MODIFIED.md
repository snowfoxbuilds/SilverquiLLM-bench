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

## Item 4: sos_13 — Emeritus of Truce // Swords to Plowshares oracle impl

### Tests
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_13/tests.py` — 6 tests: identity, ETB token via cast_spell with player targeting, token characteristics (2/1 flying), prepared back-face exile+lifegain, prepared rejection, CMC invariant

### Implementation
- `benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_13/card_impl.py` — Full oracle impl: Creature {1}{W}{W} CMC 3, dual-mode (front=ETB 2/1 Inkling to target player, back=exile creature+lifegain via prepared from exile), uses TargetRequirement, on_resolve handles both faces
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_13/__init__.py` — Package init for test directory
- `benchmarks/sos/data/tests/audited/sos/sos_13/tests.py` — Copy of rewritten tests to audited location

## Item 5: sos_57 — Mana Sculpt oracle impl (FLAGSHIP)

### Tests
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_57/tests.py` — 9 tests: identity (5 basic), counter spell, get_targets finds stack spells, excludes permanents, does not affect non-targets

### Implementation
- `benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_57/card_impl.py` — Full oracle: Instant {1}{U}{U} CMC 3, get_targets returns stack objects, on_resolve counters target spell (removes from stack, moves to owner's GY), fizzle check if target removed, Wizard-conditional colorless mana refund
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_57/__init__.py` — Package init for test directory
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_57/tests.py` — Copy of tests for workspace execution

## Item 6: sos_97 — Ral Zarek, Guest Lecturer oracle impl

### Tests
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_97/tests.py` — 12 tests covering identity, abilities, edge cases, interactions

### Implementation
- `benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_97/card_impl.py` — Full oracle: Planeswalker {1}{B}{B} loyalty 3, four loyalty abilities (+1 surveil, -1 discard, -2 GY return, -7 coin flip), get_targets, get_valid_targets_for_ability, on_resolve ETB with target removal
- `benchmarks/sos/data/test_oracle_workspace/engine/zones.py` — Graceful fallback in move_to_zone when card not in source zone (adds to destination directly)
- `benchmarks/sos/data/test_oracle_workspace/engine/state_based_actions.py` — Added _sba_planeswalker_zero_loyalty (rule 704.5i) to move PW with 0 loyalty to graveyard
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_97/__init__.py` — Package init for test directory
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_97/tests.py` — Copy of audited tests for workspace execution

Item 6 (Revision): sos_97 — Ral Zarek, Guest Lecturer
Tests
benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_97/tests.py — 10 oracle tests (identity, abilities, surveil, discard, gy return, ultimate, insufficient loyalty, dies at 0, one-per-turn)
Implementation
benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_97/card_impl.py — Revised: proper surveil with choice mechanism, targeting via _resolve_target/_resolve_targets, removed spell-level get_targets/on_resolve

## Item 7: sos_120 — Improvisation Capstone oracle impl

### Tests
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_120/tests.py` — 12 rewritten tests: identity (no Keyword.PARADIGM), exile-from-library-until-threshold, does-not-target-opponent-creatures, cast-chosen-exiled-cards-for-free, paradigm-exiles-self, paradigm-recurring-cast across 3 turns, paradigm-offer-can-be-declined

### Implementation
- `benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_120/card_impl.py` — Full oracle: Sorcery {5}{R}{R} CMC 7, exile-from-library loop until MV>=4, free-cast offers via choose_yes_no, Paradigm replacement effect (self to exile), recurring trigger from exile via BeginningOfMainPhaseEvent
- `benchmarks/sos/data/test_oracle_workspace/engine/events.py` — Added BeginningOfMainPhaseEvent triggered event for Paradigm recurring trigger
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_120/__init__.py` — Package init for test directory
- `benchmarks/sos/data/tests/audited/sos/sos_120/tests.py` — Copy of rewritten tests to audited location

Item 7 (Revision): sos_120 — Improvisation Capstone
Tests
benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_120/tests.py — 9 tests (identity, exile threshold, no-target, cast-free, decline, paradigm-self-exile, recurring 3 turns, paradigm-decline)
Implementation
benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_120/card_impl.py — Revised: skip lands in cast offers, replacement effect already uses ReplacementManager, recurring cast uses cast_spell_free pipeline
benchmarks/sos/data/test_oracle_workspace/engine/game_state.py — Wire BeginningOfMainPhaseEvent into advance_phase() on PRECOMBAT_MAIN transition

## Item 8: sos_201 — Lorehold, the Historian oracle impl

### Implementation
- `benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_201/card_impl.py` — Full oracle: Legendary Creature 5/5 {3}{R}{W}, Flying+Haste, miracle-grant continuous effect, opponent-upkeep discard-to-draw trigger
- `benchmarks/sos/data/test_oracle_workspace/engine/casting.py` — Added cast_spell_for_cost() for miracle alt-cost casting primitive
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_201/__init__.py` — Package init for test directory
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_201/tests.py` — Copy of audited tests for workspace execution

## Item 9: sos_226 — Silverquill, the Disputant oracle impl

### Tests
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_226/tests.py` — 7 rewritten tests covering identity, no-get_targets, casualty mechanics, and cleanup

### Implementation
- `benchmarks/sos/data/test_oracle_workspace/cards/sos/sos_226/card_impl.py` — Legendary Creature 4/4 {2}{W}{B}, Flying+Vigilance, casualty_grant=1 attribute for engine detection
- `benchmarks/sos/data/test_oracle_workspace/engine/casting.py` — Added _handle_casualty() primitive: scans bf for casualty granters, offers sac, copies spell
- `benchmarks/sos/data/test_oracle_workspace/tests/audited/sos/sos_226/__init__.py` — Package init for test directory
- `benchmarks/sos/data/tests/audited/sos/sos_226/tests.py` — Copy of rewritten tests to benchmarks location
