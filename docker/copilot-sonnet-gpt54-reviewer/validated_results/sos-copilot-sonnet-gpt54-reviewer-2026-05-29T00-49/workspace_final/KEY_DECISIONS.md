
## engine/zones.py: replacement effects fire for all zone moves (not just leaving_battlefield)
Removing the `and leaving_battlefield` guard in `move_to_zone` allows replacement effects to intercept stack→graveyard moves. This is needed for "exile instead of graveyard" effects. Established in sos_1 implementation.

## engine/casting.py: _resolve_spell creates MoveToGraveyardReplacementEvent
Non-permanent spells moving from stack to graveyard on resolution now go through replacement event consultation. This enables exile-instead-of-graveyard replacement effects (e.g., Dawning Archaic attack trigger). Established in sos_1.

## Cast-from-graveyard convention
Use `cast_spell_free(game, controller, target_card, Zone.GRAVEYARD)` for free-cast-from-graveyard effects. Established in sos_1.

## Token colors convention
Set `token.colors = {"white", "black"}` etc as a simple attribute on the token object. Established in sos_13.

## immediate=True for ETB triggers (test convention)
When tests fire events synchronously via `trigger_manager.fire_event()`, ETB triggers need `immediate=True` to execute synchronously. This is a test infrastructure convention. Established in sos_13.

## Turn skipping engine support
Player.turns_to_skip attribute checked at start of run_turn() in engine/turn.py. Decremented each skip. Established in sos_97.

## Surveil implementation pattern
Surveil N: read top N cards from library, put chosen into graveyard via move_to_zone, rest remain on top. Established in sos_97.

## BeginningOfPrecombatMainTriggeredEvent
Added to engine/events.py for Paradigm mechanic (sos_120). Used for "at beginning of each of your first main phases" triggers.

## Paradigm mechanic pattern
1. On resolve: set has_resolved_once=True, exile self (replacement effect checks event.card_obj)
2. Register trigger in on_resolve() that fires on BeginningOfPrecombatMainTriggeredEvent
3. Trigger allows casting a copy from exile
Established in sos_120.

## Casualty mechanic convention
Grant via apply_casualty_grant() method: sets casualty_threshold=1 on eligible cards in hand. Full spell-copy implementation requires engine API not yet available. Established in sos_226.

## Affinity for creatures convention
- Self-affinity: count ALL creatures controller controls including this card
- Granted affinity (to instants/sorceries): exclude the granting creature from count (per tests)
- Global cost reducer cleanup: check if source is still on battlefield before applying reduction
Established in sos_245.

## Land-that-animates-to-creature pattern
Set damage_marked=0, power/toughness properties, register_triggers() in activation effect. Don't inherit from Creature — set fields directly. Established in sos_257.
