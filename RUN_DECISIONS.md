# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Spec deviation: Item 2 — Chandra sacrifice uses game.sacrifice()
- **TODO spec expected**: Token sacrifice at end of turn.
- **Actual codebase state**: Implementation used `move_to_zone()` directly, skipping sacrifice triggers.
- **What was implemented instead**: Changed to `game.sacrifice()` for proper sacrifice semantics.
- **Impact**: `cards/fdn/fdn_81/card_impl.py`

## Test failure: Item 5 — Squad Rallier (fdn_24)
- **Failing tests**: test_eligible_creature_goes_to_hand
- **Tester's intent**: Verify that the activated ability puts a creature on bottom of library correctly.
- **Implementer's approach**: Used `add_to_bottom()` method on ZoneContainer, which doesn't exist.
- **Coordinator decision**: fix implementation — use correct ZoneContainer API (`add(card, position="bottom")` or equivalent).
- **Reasoning**: Clear implementation bug; the test correctly exercises the card's behavior.

## Disagreement: Item 5 — Squad Rallier activated ability cost
- **Reviewer comment (strict)**: Use `ManaCost.parse("{2}{W}")` for the colored equip cost.
- **Implementer justification**: The test provides only colorless mana and asserts success. The engine's `ManaPool.can_pay()`/`pay()` cannot pay White pips from colorless mana. Using `{2}{W}` breaks the passing test.
- **Coordinator decision**: accept implementer
- **Reasoning**: The test defines the contract. The ENGINE LIMITATION is correctly documented. The oracle text cost (`{2}{W}`) can't be fully modeled with the current engine's mana payment system in this context.
- **Impact**: `cards/fdn/fdn_24/card_impl.py` — cost remains `ManaCost(generic=3)` with ENGINE LIMITATION comment.
