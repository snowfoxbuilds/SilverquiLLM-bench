# Engine API Reference

Auto-generated from engine source. For agent consumption.

## Modules

### abilities

- **class `AbilityError`** — Raised when an ability activation is illegal.
- **dataclass `ActivatedAbilityInstance`** — Runtime representation of an activated ability.  
  Fields: `source: Any`, `controller: Any`, `cost: Callable[..., bool]`, `effect: Callable[..., None]`, `is_mana_ability: bool`, `description: str`
- **dataclass `LoyaltyAbilityInstance`** — Runtime representation of a planeswalker loyalty ability.  
  Fields: `source: Any`, `controller: Any`, `loyalty_cost: int`, `effect: Callable[..., None]`, `description: str`
- `clear_loyalty_tracking() -> None` — Clear the loyalty-activated-this-turn tracker.
- `tap_cost(game: GameState, source: Any) -> bool` — Generic tap-cost function.
- `activate_ability(game: GameState, player: Any, ability: ActivatedAbilityInstance | LoyaltyAbilityInstance) -> None` — Activate an ability.

### card

- **dataclass `Mode`** — Represents a single mode of a modal spell or ability.  
  Fields: `name: str`, `description: str`
- **dataclass `ActivatedAbility`** — An activated ability on a permanent.  
  Fields: `cost: Callable[..., Any]`, `effect: Callable[..., Any]`, `description: str`
- **dataclass `LoyaltyAbility`** — A planeswalker loyalty ability.  
  Fields: `loyalty_cost: int`, `effect: Callable[..., Any]`, `description: str`
- **dataclass `ManaAbility`** — A mana ability (does not use the stack).  
  Fields: `cost: Callable[..., Any]`, `mana_produced: Callable[..., Any]`, `description: str`
- **dataclass `ContinuousEffect`** — A continuous effect applied by an enchantment or other source.  
  Fields: `apply: Callable[..., Any]`, `remove: Callable[..., Any]`, `description: str`
- **class `GameObject`** — Base class for anything that can exist in a zone.  
  - `reset_id_counter(cls) -> None`
- **class `CardImpl`** — Abstract base for all card implementations.  
  - `can_cast(game: GameState) -> bool`  
  - `on_cast(game: GameState) -> None`  
  - `on_resolve(game: GameState) -> None`  
  - `get_targets(game: GameState) -> list[Any]`  
  - `register_triggers(game: GameState) -> None`  
  - `register_replacement_effects(game: GameState) -> None`  
  - `get_activated_abilities() -> list[ActivatedAbility]`  
  - `get_modes() -> list[Mode]`
- **class `Creature`** — A creature card.  
  - `power() -> int`  
  - `toughness() -> int`
- **class `Instant`** — An instant spell — no extra fields beyond CardImpl.
- **class `Sorcery`** — A sorcery spell — no extra fields beyond CardImpl.
- **class `Enchantment`** — An enchantment card.  
  - `apply_continuous_effect(game: GameState) -> None`  
  - `on_enchant(game: GameState) -> None`  
  - `on_detach(game: GameState) -> None`
- **class `Aura`** — An Aura enchantment — attaches to a permanent on the battlefield.
- **class `Artifact`** — An artifact card.
- **class `ArtifactCreature`** — An artifact creature — combines Artifact and Creature types.
- **class `Planeswalker`** — A planeswalker card.  
  - `get_loyalty_abilities() -> list[LoyaltyAbility]`
- **class `Land`** — A land card.  
  - `can_cast(game: GameState) -> bool`  
  - `get_mana_abilities() -> list[ManaAbility]`

### casting

- **class `CastingError`** — Raised when a spell cast or land play is illegal.
- `is_sorcery_speed(game: GameState, player: Player) -> bool` — Return ``True`` if sorcery-speed timing is met for *player*.
- `can_cast_at_instant_speed(card: CardImpl) -> bool` — Return ``True`` if *card* may be cast at instant speed.
- `cast_spell(game: GameState, player: Player, card: CardImpl) -> None` — Cast *card* from *player*'s hand.
- `play_land(game: GameState, player: Player, land_card: CardImpl) -> None` — Play *land_card* from *player*'s hand onto the battlefield.

### combat

- **dataclass `CombatState`** — Tracks attackers, blockers, damage assignments, and block ordering.  
  Fields: `attackers: dict[Any, Player]`, `blockers: dict[Any, list[Any]]`, `attacker_blockers: dict[Any, list[Any]]`, `damage_assignments: dict[Any, list[tuple[Any, int]]]`, `was_blocked: set[Any]`, `in_combat: bool`
- `declare_attackers_step(game: GameState) -> None` — Declare attackers step: active player chooses creatures to attack with.
- `declare_blockers_step(game: GameState) -> None` — Declare blockers step: defending player assigns blockers.
- `combat_damage_step(game: GameState) -> None` — Combat damage step: deal combat damage.
- `end_combat_step(game: GameState) -> None` — End combat step: remove from combat and clear combat state.

### continuous_effects

- **enum `Layer`** — The 7 layers for applying continuous effects (rule 613).  
  Members: `COPY`, `CONTROL`, `TEXT`, `TYPE`, `COLOR`, `ABILITY`, `POWER_TOUGHNESS`
- **enum `SubLayer`** — Sub-layers for layer 7 (power/toughness) effects.  
  Members: `CHARACTERISTIC_DEFINING`, `SET_PT`, `MODIFY_PT`, `COUNTERS`
- **dataclass `ContinuousEffect`** — A single continuous effect in the layer system.  
  Fields: `source: Any`, `layer: Layer`, `sublayer: SubLayer | None`, `apply: Callable[..., Any]`, `timestamp: int`, `duration: int`
- **class `EffectManager`** — Manages all active continuous effects and applies them in layer order.  
  - `add(effect: ContinuousEffect) -> ContinuousEffect`  
  - `remove(effect: ContinuousEffect) -> bool`  
  - `remove_expired(game: GameState) -> int`  
  - `apply_all(game: GameState) -> None`  
  - `effects() -> list[ContinuousEffect]`  
  - `get_effects_for_layer(layer: Layer) -> list[ContinuousEffect]`  
  - `get_effects_by_source(source: Any) -> list[ContinuousEffect]`  
  - `clear() -> None`

### game

- `create_game(player1: Player, player2: Player, deck1: list[CardImpl], deck2: list[CardImpl]) -> GameState` — Create and initialise a new two-player game.
- `deal_damage(game: GameState, source: Any, target: Any, amount: int) -> None` — Deal *amount* damage from *source* to *target*.
- `destroy(game: GameState, permanent: Any) -> None` — Destroy *permanent* — move it from the battlefield to its owner's graveyard.
- `sacrifice(game: GameState, player: Player, permanent: Any) -> None` — Sacrifice *permanent* — move it from the battlefield to its owner's graveyard.
- `exile(game: GameState, obj: Any) -> None` — Exile *obj* — move it to its owner's exile zone.
- `draw_card(game: GameState, player: Player) -> Any | None` — Draw a card for *player* — move the top card of library to hand.
- `discard(game: GameState, player: Player, card: Any) -> None` — Discard *card* from *player*'s hand to the owner's graveyard.
- `create_token(game: GameState, player: Player, token: Any) -> None` — Create a token on the battlefield under *player*'s control.
- `add_counter(game: GameState, permanent: Any, counter_type: str, amount: int) -> None` — Add *amount* counters of *counter_type* to *permanent*.
- `remove_counter(game: GameState, permanent: Any, counter_type: str, amount: int) -> None` — Remove *amount* counters of *counter_type* from *permanent*.
- `tap(game: GameState, permanent: Any) -> None` — Tap *permanent* — set ``is_tapped = True``.
- `untap(game: GameState, permanent: Any) -> None` — Untap *permanent* — set ``is_tapped = False``.
- `run_game(game: GameState) -> Player | None` — Run the game loop until the game ends.

### game_state

- **class `GameState`** — Central game-state object tracking all mutable game information.  
  - `active_player() -> Player`  
  - `priority_player() -> Player`  
  - `non_active_player() -> Player`  
  - `get_battlefield(player: Player) -> ZoneContainer`  
  - `get_hand(player: Player) -> ZoneContainer`  
  - `get_graveyard(player: Player) -> ZoneContainer`  
  - `get_library(player: Player) -> ZoneContainer`  
  - `get_exile(player: Player) -> ZoneContainer`  
  - `advance_phase() -> None`  
  - `empty_mana_pools() -> None`

### mana

- **class `ManaPool`** — Tracks available mana for a player.  
  - `add(mana_type: ManaType, amount: int) -> None`  
  - `empty() -> None`  
  - `total() -> int`  
  - `get(mana_type: ManaType) -> int`  
  - `last_payment_colors() -> list[Color]`  
  - `can_pay(cost: ManaCost) -> bool`  
  - `pay(cost: ManaCost, choices: dict[ManaType, int] | None) -> bool`

### player

- **class `ScriptExhaustedError`** — Raised when a DeterministicPlayer's script runs out of predetermined answers.
- **class `Player`** — Abstract base class for all players in the game.  
  - `choose_target(options: Any, requirement: Any) -> Any`  
  - `choose(options: Any, description: str) -> Any`  
  - `choose_yes_no(prompt: str) -> bool`  
  - `assign_damage_order(attackers_or_blockers: Any) -> list[Any]`  
  - `choose_card(cards: Any, description: str) -> Any`
- **class `DeterministicPlayer`** — A scripted player for testing that returns predetermined answers.  
  - `remaining_choices() -> int`  
  - `choose_target(options: Any, requirement: Any) -> Any`  
  - `choose(options: Any, description: str) -> Any`  
  - `choose_yes_no(prompt: str) -> bool`  
  - `assign_damage_order(attackers_or_blockers: Any) -> list[Any]`  
  - `choose_card(cards: Any, description: str) -> Any`

### replacement_effects

- **dataclass `ReplacementEffect`** — Describes a single replacement effect.  
  Fields: `event_type: str`, `source: Any`, `condition: Callable[..., bool] | None`, `replacement: Callable[..., dict[str, Any]]`, `controller: Player | None`
- **class `ReplacementManager`** — Central registry for replacement effects.  
  - `register(effect: ReplacementEffect) -> None`  
  - `unregister(source: Any) -> None`  
  - `apply(game: GameState, event_type: str, event_data: dict[str, Any]) -> dict[str, Any]`  
  - `get_effects() -> list[ReplacementEffect]`  
  - `get_effects_for_source(source: Any) -> list[ReplacementEffect]`  
  - `clear() -> None`

### stack

- **dataclass `StackObject`** — An object on the stack representing a spell or ability.  
  Fields: `source: Any`, `controller: Player`, `targets: list[Any]`, `on_resolve: Callable[[GameState], None]`, `is_mana_ability: bool`
- **class `Stack`** — The game stack — a LIFO structure for spells and abilities.  
  - `push(obj: StackObject) -> None`  
  - `pop() -> StackObject`  
  - `peek() -> StackObject | None`  
  - `is_empty() -> bool`  
  - `objects() -> list[StackObject]`
- `check_state_based_actions(game: GameState) -> None` — Check and perform all state-based actions until the game state is stable.
- `priority_loop(game: GameState) -> None` — Run the priority-passing loop for the current phase/step.

### state_based_actions

- `check_state_based_actions(game: GameState) -> bool` — Perform a single pass of all state-based actions.
- `resolve_state_based_actions(game: GameState) -> bool` — Run state-based actions in a loop until no more actions are taken.

### triggers

- **enum `EventType`** — Game events that can trigger abilities.  
  Members: `ENTERS_BATTLEFIELD`, `LEAVES_BATTLEFIELD`, `DEALS_DAMAGE`, `LOSES_LIFE`, `GAINS_LIFE`, `DRAWS_CARD`, `BEGINNING_OF_UPKEEP`, `BEGINNING_OF_COMBAT`, `END_OF_TURN`, `CREATURE_DIES`, `SPELL_CAST`, `ATTACKS`, `BLOCKS`
- **dataclass `TriggerRegistration`** — Describes a single triggered ability.  
  Fields: `event_type: EventType`, `condition: Callable[..., bool] | None`, `effect: Callable[..., None]`, `source: Any`, `controller: Player`
- **class `TriggerManager`** — Central registry for triggered abilities.  
  - `register(trigger: TriggerRegistration) -> None`  
  - `unregister(source: Any) -> None`  
  - `fire_event(game: GameState, event_type: EventType, data: dict[str, Any] | None) -> None`  
  - `get_triggers() -> list[TriggerRegistration]`  
  - `get_triggers_for_source(source: Any) -> list[TriggerRegistration]`  
  - `clear() -> None`

### turn

- `run_turn(game: GameState) -> None` — Execute a full turn, iterating through all phases/steps.

### types

- **enum `Color`** — The five colors of Magic.  
  Members: `WHITE`, `BLUE`, `BLACK`, `RED`, `GREEN`
- **enum `ManaType`** — Mana types including colorless.  
  Members: `WHITE`, `BLUE`, `BLACK`, `RED`, `GREEN`, `COLORLESS`
- **enum `Zone`** — Game zones.  
  Members: `BATTLEFIELD`, `HAND`, `LIBRARY`, `GRAVEYARD`, `EXILE`, `STACK`, `COMMAND`
- **enum `Phase`** — Turn phases.  
  Members: `BEGINNING`, `PRECOMBAT_MAIN`, `COMBAT`, `POSTCOMBAT_MAIN`, `ENDING`
- **enum `Step`** — Turn steps.  
  Members: `UNTAP`, `UPKEEP`, `DRAW`, `BEGIN_COMBAT`, `DECLARE_ATTACKERS`, `DECLARE_BLOCKERS`, `COMBAT_DAMAGE`, `END_COMBAT`, `END`, `CLEANUP`
- **enum `CardType`** — Card types.  
  Members: `CREATURE`, `INSTANT`, `SORCERY`, `ENCHANTMENT`, `ARTIFACT`, `PLANESWALKER`, `LAND`
- **enum `Supertype`** — Card supertypes.  
  Members: `BASIC`, `LEGENDARY`, `SNOW`
- **enum `Keyword`** — Evergreen keyword abilities (combinable via bitwise OR).  
  Members: `FLYING`, `FIRST_STRIKE`, `DOUBLE_STRIKE`, `DEATHTOUCH`, `TRAMPLE`, `LIFELINK`, `VIGILANCE`, `REACH`, `HASTE`, `FLASH`, `DEFENDER`, `HEXPROOF`, `INDESTRUCTIBLE`, `MENACE`, `WARD`
- **dataclass `ManaCost`** — Represents a mana cost.  
  Fields: `generic: int`, `pips: dict[ManaType, int]`, `x_count: int`
- **dataclass `TargetRequirement`** — Describes a targeting requirement for a spell or ability.  
  Fields: `filter_fn: Callable[..., Any]`, `description: str`, `zone: Zone`

### zones

- **class `IllegalMoveError`** — Raised when a zone move is illegal (e.g. object not found in source zone).
- **class `ZoneContainer`** — Wraps an ordered list of game-object references for a single zone.  
  - `add(obj: Any, position: str) -> None`  
  - `remove(obj: Any) -> None`  
  - `shuffle() -> None`  
  - `contains(obj: Any) -> bool`  
  - `get_all() -> list[Any]`  
  - `top(n: int) -> list[Any]`  
  - `bottom(n: int) -> list[Any]`
- **class `Zones`** — Per-player collection mapping each :class:`Zone` to a :class:`ZoneContainer`.  
  - `new_player(cls) -> Zones`
- `move_zone(obj: Any, from_zone: ZoneContainer, to_zone: ZoneContainer, position: str) -> None` — Move *obj* from *from_zone* to *to_zone*.
