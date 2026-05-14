# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Upgrade 4 simplified Aura implementations to full oracle text

### Tests
- `tests/audited/fdn/fdn_26/tests.py` — stub (no audited tests yet)
- `tests/audited/fdn/fdn_156/tests.py` — stub (no audited tests yet)
- `tests/audited/fdn/fdn_168/tests.py` — stub (no audited tests yet)
- `tests/audited/fdn/fdn_213/tests.py` — stub (no audited tests yet)

### Implementation
- `cards/fdn/fdn_26/card_impl.py` — Added apply_continuous_effect() hook, cleaned imports, structured Layer 6 double strike grant
- `cards/fdn/fdn_156/card_impl.py` — Split single effect into Layer 4 (type) + Layer 6 (ability) separate ContinuousEffects, added ENGINE LIMITATION for mana ability
- `cards/fdn/fdn_168/card_impl.py` — Split into 4 layers: Layer 4 (type/name), Layer 5 (color), Layer 6 (ability), Layer 7b (SET_PT), added Color import
- `cards/fdn/fdn_213/card_impl.py` — Added apply_continuous_effect() hook, extracted _count_forests() helper, cleaned imports


## Item 2: Upgrade 3 simplified Planeswalker implementations to full oracle text

### Tests
- `tests/audited/fdn/fdn_44/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_81/tests.py` — Stub (no audited tests yet)
- `tests/audited/fdn/fdn_234/tests.py` — Stub (no audited tests yet)

### Implementation
- `cards/fdn/fdn_44/card_impl.py` — Full rewrite: passive properly guards on combat flag, +1 loot, −2 Ninja token, −9 emblem via SPELL_CAST trigger
- `cards/fdn/fdn_81/card_impl.py` — Full rewrite: +2 uses choose_card() to pick one exiled card as playable, +1 uses sacrifice() and END_STEP event, −4 supports _damage_assignments
- `cards/fdn/fdn_234/card_impl.py` — Full rewrite: +1 uses choose_card() for optional creature/land selection, −3 lazy revalidation, −8 ContinuousEffect emblem
- `engine/triggers.py` — Added END_STEP event type to EventType enum
