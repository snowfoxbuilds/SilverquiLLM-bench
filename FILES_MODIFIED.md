# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.


## Item 1: Fix is_aura default True in _sba_aura_unattached

### Implementation
- `engine/state_based_actions.py` — Changed getattr default for is_aura from True to False

## Item 2: Wire SBA trigger queueing in resolve_state_based_actions()

### Tests
- `tests/engine/test_state_based_actions.py` — Existing SBA tests (56 passed, no new test file from tester)

### Implementation
- `engine/state_based_actions.py` — Fire CREATURE_DIES/LEAVES_BATTLEFIELD events in _move_to_graveyard(); add trigger-aware outer loop in resolve_state_based_actions()

## Item 3: Centralize zone-transition hooks into move_to_zone()

### Implementation
- `engine/zones.py` — Added move_to_zone() function with replacement effects, event firing, and trigger registration/unregistration hooks
- `engine/game.py` — Refactored destroy(), sacrifice(), exile() to delegate to move_to_zone()
- `engine/state_based_actions.py` — Refactored _move_to_graveyard() to delegate to move_to_zone()
- `engine/casting.py` — Refactored _resolve_spell() to use move_to_zone() for both permanent (STACK→BATTLEFIELD) and non-permanent (STACK→GRAVEYARD) spells

## Item 4: Batch 1 — Remaining vanilla & French vanilla creatures

### Tests
- `tests/cards/test_vanilla_creatures_batch2.py` — 45 tests for 7 Scryfall-verified FDN creatures (stats, keywords, registry, integration)

### Implementation
- `cards/foundations/vanilla_creatures_batch2.py` — Rewrote to 7 real FDN creatures: Fire Elemental, Gigantosaurus, Quakestrider Ceratops, Elementalist Adept, Skyraker Giant, Swiftblade Vindicator, Zetalpa Primal Dawn

## Item 5: Batch 2 — Simple non-targeted instants & sorceries

### Tests
- `tests/cards/test_simple_spells_batch2.py` — 63 tests for 15 FDN non-targeted instants/sorceries (draw, lifegain, tokens, each-player effects, registry)

### Implementation
- `cards/foundations/simple_spells_batch2.py` — 15 new FDN spells: Embrace the Paradox, Rapturous Moment, Wisdom of Ages, Pursue the Past, Seize the Spoils, Group Project, Muse's Encouragement, Visionary's Dance, Antiquities on the Loose, Fractal Anomaly, Snarl Song, Send in the Pest, Withering Curse, Social Snub, Pox Plague
- `engine/game.py` — Added `cards_drawn_this_turn` tracking in `draw_card()` for Fractal Anomaly counter support
