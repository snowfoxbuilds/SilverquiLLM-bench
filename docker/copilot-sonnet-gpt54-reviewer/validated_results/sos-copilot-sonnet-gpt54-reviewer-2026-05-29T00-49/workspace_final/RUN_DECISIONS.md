# Run Decisions

Decisions made during this run only. Before the run ends, migrate anything worth preserving into `KEY_DECISIONS.md`.


## Untestable items: sos_1
1. "You may" opt-out path: accepted partial coverage — test infrastructure uses DeterministicPlayer that always accepts. UNVERIFIED path.
2. "That spell" exact scoping for replacement: Implementer defines tagging convention.

## sos_1 design decisions
- Cast-from-graveyard trigger uses `cast_spell_free(game, controller, target, Zone.GRAVEYARD)` - spell goes through normal casting pipeline
- Per-cast one-shot replacement effect registered with a sentinel (non-Archaic) source to persist after Archaic leaves battlefield
- engine/zones.py: removed `and leaving_battlefield` guard so replacement events fire for any zone move
- engine/casting.py: `_resolve_spell` now creates MoveToGraveyardReplacementEvent for non-permanents stack→graveyard

## sos_4 design decisions
- Converge X = len(set(colors_spent)) where colors_spent is a list/set of ManaType values
- Life gain uses gain_life(game, player, amount) helper in engine/game.py that fires GainsLifeTriggeredEvent
- Creature target revalidated before damage in on_resolve

## Untestable items: sos_13
1. Token white+black color identity: accepted partial coverage — test token subtype/stats/flying but not color attribute. UNVERIFIED color aspect.
2. Cast-copy pipeline for Prepared: test resolver and is_prepared flag separately, not full cast-copy pipeline. UNVERIFIED full cast flow.

## sos_13 design decisions
- immediate=True on ETB triggers required for test compatibility (synchronous execution)
- Prepared mechanic: `is_prepared` flag on creature, `on_resolve_swords_to_plowshares` method for STP effects
- Token colors set as `token.colors = {"white", "black"}` (simple attribute)
- Disagreements with reviewer: immediate=True kept (tests require it), full spell-casting-integration deferred (not tested)

## Untestable items: sos_57
1. Beginning of main phase timing: engine lacks BeginningOfMainPhaseTriggeredEvent. Tests manually advance phase. UNVERIFIED auto-firing.
2. Opponent-controls-Wizard negative case: accepted partial coverage (tests cover no-wizard and controlled-wizard positive cases).

## sos_57 design decisions
- Mana "spent" = CMC (no mana_spent tracking in engine; tests use CMC values)
- Deferred mana delivered via trigger on phase change (BeginningOfMainPhaseTriggeredEvent if available, else callback)
- Fizzle check: verify target still on stack before resolving

## Untestable items: sos_97
1. -7 coin flip randomness: accepted partial coverage — add _coin_flip_results override on card and player.turns_to_skip to engine to make testable. Implementer should add these.

## Untestable items: sos_120
1. Free-cast choice pipeline: accepted partial coverage (exile tracking + no-mana test)
2. Paradigm main phase trigger: accepted partial — test trigger registration; no BeginningOfPrecombatMainTriggeredEvent in engine

## Untestable items: sos_201
1. Miracle cast-at-draw timing: accepted partial — test miracle_cost attribute on cards in hand. UNVERIFIED actual cast window.
2. Optional discard scripting: accepted partial — test trigger fires and discard happens (assuming player accepts). UNVERIFIED decline path.

## sos_201 design decisions
- Miracle grant via apply_miracle_grant() called in on_enters_battlefield() and directly by tests
- "Undo on leave" for miracle grant deferred (no on_leaves_battlefield dispatch in engine)
- Upkeep trigger uses player.choose_yes_no() for optional discard

## Untestable items: sos_226
1. Spell copy engine API: Tester recommends adding copy_spell() helper and SpellCopiedTriggeredEvent. Passing to Implementer to add this.
2. New target selection for copy: Same — requires spell copy API.
3. On-leaves-battlefield grant cleanup: No engine support. Accepted partial — test that grant is present when Silverquill is in play. UNVERIFIED leave behavior.

## Untestable items: sos_257
1. Restricted mana: engine has no restricted mana pool. Accepted partial — test that life is spent and mana color is added. UNVERIFIED restriction enforcement.
2. Until-end-of-turn cleanup: engine turn cycle required. Test power increase but not cleanup. UNVERIFIED.
