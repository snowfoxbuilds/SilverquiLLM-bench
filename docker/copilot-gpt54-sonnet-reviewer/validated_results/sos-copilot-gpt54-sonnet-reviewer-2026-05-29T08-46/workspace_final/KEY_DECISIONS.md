# Key Decisions

Persistent decisions carried across runs.

- Graveyard-cast spell exile replacement should be modeled through the shared stack-to-zone move pipeline so the same effect covers both normal resolution and countered-spell paths.
- Permanent enters-the-battlefield abilities should be implemented as ETB triggers registered through `register_triggers`, not by running the effect directly from `on_resolve`.
- Cards that scale from mana actually spent should read casting metadata recorded during payment (for example `mana_spent_total` / `colors_spent`) rather than deriving from printed mana cost.
- Effects that wait for a later phase should use the shared delayed-action queue on `GameState` instead of per-card ad hoc polling.
- Planeswalker loyalty abilities should expose public targeting metadata through `LoyaltyAbility` so tests and shared engine code can reason about target contracts.
- Coin flips and skip-next-turn effects should use shared game/game-state helpers rather than card-specific state so deterministic tests can inspect both results and turn consumption.
- Recurring spell mechanics should self-exile through the shared zone-move replacement pipeline and schedule later recasts through the delayed-action queue; generated copies should carry an explicit marker so they do not recreate the recurring loop.
- Miracle support should use shared public card metadata helpers plus shared game-state tracking for first-draw windows and reveal/cast cleanup, rather than card-specific miracle flags.
- Battlefield-granted spell mechanics should expose card-level `get_granted_*` hooks that casting-time helpers scan from the controller's battlefield, rather than baking the grant into the spell cards themselves.
- Card-specific mana restrictions should attach restriction metadata to mana units in the shared mana pool and let the casting pipeline enforce legality, instead of hard-coding payment checks in each card.
