# Key Decisions

Persistent architectural and convention decisions across runs. Periodically drained into specs/ADRs

## Docker stdout/stderr direct-write carve-out

`_drain_pipe` in `silverquillm/runner.py` streams Docker stdout/stderr directly to
`run_dir/docker_stdout.log` and `run_dir/docker_stderr.log` in real time (append mode,
line-buffered, UTF-8 with error replacement). This intentionally breaks the general
`.tmp` → `.log` → harvest-copy convention used by other output files. The `.tmp` files
in `output/` are still written for backward compatibility and local diagnostics, but
the authoritative real-time logs live in `run_dir`. `_harvest_results` in `cli.py`
skips these two files since they are already present in `run_dir`.


## Oracle workspace stub detection uses AST parsing

- **Context**: The harness needs to detect which `card_impl.py` files are real oracle implementations vs empty stubs.
- **Decision**: `_is_stub_impl()` uses Python's AST module to check if any class defines a non-dunder method (e.g., `on_resolve`, `can_cast`, `get_targets`). Classes that only have `__init__` with attribute assignments are still stubs.
- **Reasoning**: Simple text-matching or regex could be fooled. AST parsing is robust and aligns with the semantics: a card impl is "real" when it defines game logic methods.
- **Impact**: `tests/test_audited_against_reference.py`

## resolve_top() vs _resolve_top_of_stack() semantics

- **Context**: The oracle workspace `test_utils.py` needed both a "resolve one stack object" helper and the existing "drain full stack" behavior.
- **Decision**: `resolve_top()` resolves exactly one stack object (pop + resolve + SBA). `_resolve_top_of_stack()` drains the entire stack with a while loop. `cast_spell()` uses `_resolve_top_of_stack()` to drain all triggers.
- **Reasoning**: Tests need fine-grained control (resolve one thing at a time) while `cast_spell()` needs the convenience of auto-draining.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/test_utils.py`


## Spell-to-graveyard replacement effect mechanism (oracle workspace engine)

- **Context**: Cards that route spells to exile on resolution (instead of graveyard) need the engine to consult replacement effects during spell resolution.
- **Decision**: Modified `_resolve_spell` in oracle workspace's `engine/casting.py` to fire a `_SpellToGraveyardReplacementEvent` and consult the `ReplacementManager` before moving instant/sorcery spells to graveyard. The replacement's `destination` field determines actual zone.
- **Reasoning**: Without this, registered replacement effects had no actual effect on the engine's resolution path.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/engine/casting.py` — oracle workspace only (ADR-010).

## Attack trigger targeting uses condition-callback lock-in

- **Context**: "Whenever ~ attacks, you may target..." triggers need targets locked when put on stack, not on resolution.
- **Decision**: Targets are locked in during the trigger's condition callback (closest available hook to "ability goes on stack"). Single-target auto-selection avoids consuming a script entry.
- **Reasoning**: The trigger system lacks a pre-resolution targeting hook. Condition check is the pragmatic alternative.
- **Impact**: Oracle card implementations using attack triggers with targeting.


## Planeswalker damage removes loyalty counters (oracle workspace engine)

- **Context**: `deal_damage()` in the oracle workspace engine needed to handle planeswalkers.
- **Decision**: Extended `deal_damage()` in `engine/game.py` to detect planeswalkers via `hasattr(target, "loyalty")` and remove loyalty counters. Check order: player → planeswalker → creature.
- **Reasoning**: MTG rules: damage to a planeswalker removes that many loyalty counters.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/engine/game.py`

## All-targets-illegal = spell countered on resolution (no effects)

- **Context**: Multi-target spells with untargeted bonus effects (like life gain) need correct handling when all targets become illegal.
- **Decision**: Per MTG rule 608.2b, if ALL targets are illegal at resolution, the spell is countered — no effects happen, including untargeted ones. Untargeted effects only resolve if at least one target remains legal.
- **Reasoning**: Matches official MTG comprehensive rules.
- **Impact**: Oracle card implementations with mixed targeted/untargeted effects.


## Planeswalker zero-loyalty SBA (oracle workspace engine)

- **Context**: MTG rule 704.5i requires planeswalkers with 0 loyalty to be put into owner's graveyard as a state-based action.
- **Decision**: Added planeswalker-0-loyalty check to `check_state_based_actions()` in oracle workspace engine.
- **Reasoning**: Required for test_dies_at_zero_loyalty to pass; fundamental MTG rule.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/engine/` — oracle workspace only.

## Surveil uses scripted choices (oracle workspace engine)

- **Context**: Surveil N requires looking at top N cards and choosing which to put in graveyard vs keep on top.
- **Decision**: Surveil implementation consults player's scripted choices to determine card disposition rather than always milling all cards.
- **Reasoning**: Matches MTG rules for surveil; enables testing both "all to gy" and "keep some on top" paths.
- **Impact**: Oracle workspace planeswalker impls and tests using surveil.


## Paradigm mechanic: replacement effect + recurring trigger (oracle workspace)

- **Context**: Paradigm is an ability word that routes a spell to exile on resolution and registers a recurring "may cast from exile" trigger at each main phase.
- **Decision**: Paradigm self-exile uses the existing `ReplacementManager` / `_SpellToGraveyardReplacementEvent` mechanism built for sos_1. Recurring trigger fires via `BeginningOfMainPhaseEvent` wired into `advance_phase()`. Recurring cast uses `cast_spell_free` for proper stack flow.
- **Reasoning**: Reuses existing engine infrastructure rather than inventing parallel mechanisms.
- **Impact**: `benchmarks/sos/data/test_oracle_workspace/engine/` and sos_120 card_impl.


## Miracle primitive: cast_spell_for_cost must mirror full casting pipeline
- **Context**: Initial miracle implementation of `cast_spell_for_cost` skipped target selection, `on_cast()`, and passed wrong args to `_resolve_spell`.
- **Decision**: `cast_spell_for_cost` must replicate the full `cast_spell` pipeline (target selection, on_cast, stack push with proper on_resolve closure, pass stack_obj to _resolve_spell) but substitute the mana cost.
- **Reasoning**: Any spell with targets or cast-time hooks would break if these steps were skipped.
- **Impact**: `engine/casting.py` — `cast_spell_for_cost()` function.

## cards_drawn_this_turn reset at turn start
- **Context**: `player.cards_drawn_this_turn` counter was only incrementing, never resetting.
- **Decision**: Reset `active_player.cards_drawn_this_turn = 0` in `advance_phase()` at the wrap-around point (new turn start).
- **Reasoning**: MTG tracks "first card drawn each turn" — counter must reset each turn per rules.
- **Impact**: `engine/game.py` — `advance_phase()`.

## Miracle trigger tracks specific event.card
- **Context**: Trigger handler was rescanning the entire hand instead of tracking which card was drawn.
- **Decision**: Use a closure variable (`_miracle_drawn_card`) shared between condition and effect functions to capture `event.card` when the trigger matches.
- **Reasoning**: Ensures correct card is offered for miracle even if hand changes between trigger and resolution.
- **Impact**: `cards/sos/sos_201/card_impl.py` miracle trigger.


## Spell copies: shallow copy + no zone movement on resolution
- **Context**: Casualty creates a copy of a spell on the stack. If the copy shares the same card object, resolving it moves the original card to graveyard.
- **Decision**: Use `copy.copy(card)` for the copy source. The copy's on_resolve executes the spell effect but does NOT perform zone movement — spell copies cease to exist after resolving per MTG rules.
- **Reasoning**: MTG rule 707.2 — copies of spells are not cards; they cease to exist instead of going to any zone.
- **Impact**: `engine/casting.py` — `_handle_casualty()` copy creation.

## Casualty hook wired into all casting entry points
- **Context**: `_handle_casualty` was only called from `cast_spell()`, missing `cast_spell_for_cost()` and `cast_spell_free()`.
- **Decision**: All three casting functions call `_handle_casualty()` after pushing the StackObject to the stack.
- **Reasoning**: Any instant/sorcery cast through any path should get the casualty offer while a granter is on the battlefield.
- **Impact**: `engine/casting.py` — all three casting functions.


## Affinity as Keyword flag + behavioral implementation
- **Context**: Affinity is parameterized ("affinity for X") but the TODO requires it as a true keyword.
- **Decision**: Added `Keyword.AFFINITY` to the enum for inspection purposes. Behavior is still implemented via `cost_reduction(game)` + the battlefield-scan grant pattern. The Keyword flag signals "has affinity" but doesn't encode what it has affinity for.
- **Reasoning**: Tests and agents need to detect "has affinity" via keyword inspection; the actual reduction logic is separate.
- **Impact**: `engine/card.py` (or types.py) Keyword enum, sos_245 card_impl.

## Multiple affinity granters stack
- **Context**: If two granters with `affinity_for_creatures_grant` are on bf, cost reduction should apply per granter.
- **Decision**: Count granters and multiply creature_count by granter_count for total reduction.
- **Reasoning**: MTG rules — multiple instances of affinity stack.
- **Impact**: `engine/casting.py` — `get_cost_reduction()`.


## Restricted mana engine primitive
- **Context**: sos_257 adds mana that can only be spent on instants/sorceries.
- **Decision**: `ManaPool.add_restricted(amount, color, restriction)` stores restricted entries. `_check_restricted_mana()` in casting.py validates at cast time — if unrestricted mana alone can't cover cost, restricted mana must be used, and spell must match restriction. CastingError raised if spell type doesn't match.
- **Reasoning**: General-purpose primitive per TODO spec; first user is sos_257's instant/sorcery restriction.
- **Impact**: `engine/casting.py`, `engine/game.py` (ManaPool).

## Persistent animation: _reset_characteristics override
- **Context**: Engine cleanup calls `_reset_characteristics()` which resets card_types to original, killing persistent animation.
- **Decision**: Cards with persistent animation override `_reset_characteristics()` to re-apply creature type after base reset if `_is_animated` is True.
- **Reasoning**: Persistent animation (no end-of-turn expiry) must survive cleanup. Only the +1/+0 boost reverts at end of turn.
- **Impact**: Pattern for any future creature-land or persistent animation card.

## on_leave_battlefield and end_of_turn_cleanup wired into engine
- **Context**: Previous items noted these hooks weren't called. Now fixed globally.
- **Decision**: `move_to_zone()` calls `on_leave_battlefield(game)` when a card leaves battlefield. `_do_cleanup_step()` calls `end_of_turn_cleanup()` on all battlefield permanents.
- **Reasoning**: Standard MTG lifecycle hooks needed by multiple cards.
- **Impact**: `engine/zones.py`, `engine/turn.py` (or game.py).

