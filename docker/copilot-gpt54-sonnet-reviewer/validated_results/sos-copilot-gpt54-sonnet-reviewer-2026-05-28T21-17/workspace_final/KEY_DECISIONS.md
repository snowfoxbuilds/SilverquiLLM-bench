# Key Decisions

Persistent decisions carried across runs.

- One-shot spell redirection can use a transient `_graveyard_destination_override` attribute on the resolving spell to send it somewhere other than the graveyard after resolution.
- Use `test_utils.cast_spell(..., payment_choices=...)` when tests need to control which colors pay generic mana for converge.
- Treat `any target` as player, creature, or planeswalker; planeswalker damage removes loyalty, then state-based actions handle zero-loyalty cleanup.
- New keyword mechanics should claim a real unused `Keyword` flag bit rather than using `Keyword(0)`, and cards that start with the keyword should refresh `_original_keywords` after constructor setup.
- When an effect needs the exact mana actually paid for a spell, record it as transient `actual_mana_spent` casting metadata and clear it on zone changes.
- For delayed effects that must wait until a player's next main phase, use `GameState.schedule_for_next_main_phase(...)` rather than assuming phase advancement stays on the internally tracked active player.
- Loyalty abilities that allow `any number of target players` should expose explicit target-declaration helpers so tests can script the full player set before resolution.
- Use scripted surveil keep-order choices and deterministic coin-flip queues in `test_utils` when card behavior depends on ordering or randomness.
- Skip-a-turn effects should enqueue a concrete per-player skip counter that the turn engine consumes when that player's turn would begin.
- Repeating effects that trigger at the beginning of each of a player's first main phases should use a dedicated first-main-phase event rather than chaining next-main-phase callbacks.
- Effects that grant casualty should allow the granting permanent itself to be sacrificed if it still satisfies the casualty power requirement.
- For optional casualty-style payments in scripted tests, an exhausted yes/no decision queue should be treated as declining the optional payment rather than crashing cast setup.
- Battlefield static abilities that reduce the cost of other spells should implement `granted_cost_reduction_for(...)`, and casting should sum those granted reductions before clamping against the generic portion of the mana cost.
- Restricted mana should be tracked in the mana pool and validated against the specific spell being cast so illegal uses leave the restricted mana unspent.
