
## Continuous Effect Pattern (sos_201, sos_226, sos_245)
Continuous effects that grant properties to cards in hand follow a clear pattern:
- Register as continuous effect in `on_enters_battlefield`
- In effect function: first clear the property from ALL hand cards, then re-grant only if source is on battlefield
- Check `if not bf.contains(source): return` for all triggers (upkeep, draw, etc)
- This ensures clean state when the source leaves the battlefield

## BeginningOfMainPhaseTriggeredEvent (engine/events.py, sos_57)
Added `BeginningOfMainPhaseTriggeredEvent(active_player)` to engine/events.py and fire it in engine/turn.py at PRECOMBAT_MAIN and POSTCOMBAT_MAIN phase entries. Trigger conditions must check `event.active_player is controller` for "your next main phase" semantics.

## Cost Reduction via cost_reduction() method (sos_1, sos_245)
Spells with cost reduction override `cost_reduction(game)` to return the number of generic mana to reduce. The casting module reads this value. Pattern established in sos_1 (graveyard-based) and sos_245 (creature-count-based).

## Paradigm / Prepared / Casualty as attribute grants
Complex keywords that grant abilities to spells during casting are implemented as attribute grants (e.g., `casualty_cost`, `miracle_cost`, `affinity_for_creatures`) set via continuous effects while the source is on the battlefield.

## Player.turns_to_skip (engine/player.py, sos_97)
Added `turns_to_skip: int = 0` to Player for turn-skip effects. Engine/turn.py honors this at turn start.
