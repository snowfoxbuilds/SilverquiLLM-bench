Phase 1: Engine & Base Set

Scope: Python project setup → core rules engine → card base classes → test utilities → MTG Foundations base set (representative subset). Phases 2 (runner/harness) and 3 (benchmark runs) are separate TODOs.

---

- [x] **Project scaffold: pyproject.toml, package layout, dev tooling**
  Detail: Initialize the Python project structure for the game engine.

  - Create `pyproject.toml` with project name `SilverquiLLM-bench`, Python >=3.11, GPL-2.0 license. Dev deps: `pytest`, `pytest-cov`, `ruff`, `mypy`. Runtime dep: `requests` (for Scryfall fetcher).
  - Directory layout:
```javascript
SilverquiLLM-bench/
  engine/
    __init__.py
  cards/
    __init__.py
    foundations/
      __init__.py
  tests/
    __init__.py
    engine/
      __init__.py
    cards/
      __init__.py
```

- Add `ruff.toml` (line-length 100, Python 3.11 target).
- Add `py.typed` marker in `SilverquiLLM-bench/`.
- Confirm: `pip install -e ".[dev]"` succeeds, `pytest` discovers zero tests, `ruff check .` passes.
- Testability: `pytest --co` returns 0 items, exit code 0.
- [x] **Core enums and type definitions**
  Detail: Define the fundamental enums and lightweight types the entire engine depends on.

  - File: `SilverquiLLM-bench/engine/types.py`
  - Enums (use `enum.Enum` / `enum.Flag` as appropriate):
    - `Color` — WHITE, BLUE, BLACK, RED, GREEN (single-letter aliases W/U/B/R/G).
    - `ManaType` — WHITE, BLUE, BLACK, RED, GREEN, COLORLESS.
    - `Zone` — BATTLEFIELD, HAND, LIBRARY, GRAVEYARD, EXILE, STACK, COMMAND.
    - `Phase` — BEGINNING, PRECOMBAT_MAIN, COMBAT, POSTCOMBAT_MAIN, ENDING.
    - `Step` — UNTAP, UPKEEP, DRAW, BEGIN_COMBAT, DECLARE_ATTACKERS, DECLARE_BLOCKERS, COMBAT_DAMAGE, END_COMBAT, END, CLEANUP (plus `None` for main phases).
    - `CardType` — CREATURE, INSTANT, SORCERY, ENCHANTMENT, ARTIFACT, PLANESWALKER, LAND.
    - `Supertype` — BASIC, LEGENDARY, SNOW.
    - `Keyword` — Flag enum for evergreen keywords: FLYING, FIRST_STRIKE, DOUBLE_STRIKE, DEATHTOUCH, TRAMPLE, LIFELINK, VIGILANCE, REACH, HASTE, FLASH, DEFENDER, HEXPROOF, INDESTRUCTIBLE, MENACE, WARD.
  - Lightweight dataclasses:
    - `ManaCost(generic: int, pips: dict[ManaType, int], x_count: int = 0)` with `cmc` property and `parse(cost_str: str) -> ManaCost` classmethod (e.g. `"{2}{W}{U}"`).
    - `TargetRequirement(filter_fn, description, zone)`.
  - Note: Defer hybrid/Phyrexian mana parsing to a later TODO — no Foundations cards need it.
  - Testability: unit tests for `ManaCost.parse` covering generic, colored, X costs, and invalid inputs.
- [ ] **Zone containers**
  Detail: Implement the zone data structures that hold game objects.

  - File: `SilverquiLLM-bench/engine/zones.py`
  - `ZoneContainer` — wraps an ordered list of `GameObject` references per zone. Methods: `add(obj)`, `remove(obj)`, `contains(obj)`, `get_all() -> list`, `shuffle()` (for library), `top(n)` / `bottom(n)` for library.
  - `Zones` — a per-player collection: `{Zone: ZoneContainer}`. Factory classmethod `Zones.new_player()` creates empty zones.
  - `move_zone(obj, from_zone, to_zone, position="top")` — removes from source, adds to destination. Raises `IllegalMoveError` if not found.
  - Edge cases: moving to library top vs bottom vs shuffle-in; moving a card already on the battlefield back to battlefield (should be a no-op).
  - Testability: test add/remove/move round-trip, shuffle changes order, top/bottom slicing.
- [ ] **Player ABC and DeterministicPlayer**
  Detail: Define the abstract player interface and a scripted test player.

  - File: `SilverquiLLM-bench/engine/player.py`
  - `Player(ABC)`:
    - Properties: `name: str`, `life: int`, `zones: Zones`, `mana_pool: ManaPool` (forward ref), `has_lost: bool`, `land_plays_remaining: int`.
    - Abstract methods: `choose_target(options, requirement) -> target`, `choose(options, description) -> choice`, `choose_yes_no(prompt) -> bool`, `assign_damage_order(attackers_or_blockers) -> ordered list`, `choose_card(cards, description) -> card`.
  - `DeterministicPlayer(Player)`:
    - Constructor takes `name: str` and `script: list[Any]` — a FIFO queue of predetermined answers.
    - Each abstract method pops the next answer from the script. Raises `ScriptExhaustedError` if script runs out.
    - Add `remaining_choices -> int` property for test assertions.
  - Testability: instantiate DeterministicPlayer with scripted choices, call abstract methods, verify correct values returned and queue drains.
- [ ] **Mana pool and cost payment**
  Detail: Implement mana production, pooling, and cost payment logic.

  - File: `SilverquiLLM-bench/engine/mana.py`
  - `ManaPool`:
    - Internal storage: `dict[ManaType, int]` (counts per mana type).
    - Methods: `add(mana_type, amount)`, `empty()` (clears pool — happens at phase/step transitions), `total() -> int`, `get(mana_type) -> int`.
    - `can_pay(cost: ManaCost) -> bool` — check whether pool satisfies cost. Generic can be paid by any type. X is treated as 0 for can_pay unless explicitly set.
    - `pay(cost: ManaCost, choices: dict[ManaType, int] | None) -> bool` — deduct mana. `choices` maps how generic cost is split across types. If `choices` is None, auto-pay greedily (prefer colorless for generic). Returns False if insufficient.
  - Hybrid/Phyrexian cost payment deferred — leave a `# TODO: hybrid` comment in `can_pay`/`pay`.
  - Testability: test adding mana, paying exact costs, paying generic with mixed colors, can_pay returning False, pool emptying.
- [ ] **GameState scaffold and turn structure**
  Detail: Build the central GameState object and the turn/phase/step progression loop.

  - File: `SilverquiLLM-bench/engine/game_state.py`
  - `GameState`:
    - Fields: `players: list[Player]`, `active_player_index: int`, `priority_player_index: int`, `phase: Phase`, `step: Step | None`, `turn_number: int`, `stack: Stack` (forward ref), `is_game_over: bool`, `winner: Player | None`.
    - Properties: `active_player`, `priority_player`, `non_active_player` (2-player assumption for v1).
    - Zone accessors: `get_battlefield(player)`, `get_hand(player)`, `get_graveyard(player)`, `get_library(player)`, `get_exile(player)`.
    - `advance_phase()` — move to the next phase/step in MTG turn order. At CLEANUP end, increment `turn_number`, swap `active_player_index`.
    - `empty_mana_pools()` — called on each phase/step transition.
  - File: `SilverquiLLM-bench/engine/turn.py`
  - `run_turn(game: GameState)` — iterate through all phases/steps of a single turn. At each priority point, call `priority_loop(game)` (stub for now — just passes).
  - Testability: create 2-player game, call `advance_phase` repeatedly, assert correct phase/step sequence and active player swap after full turn.
- [ ] **The Stack: data structure, priority passing, and resolution**
  Detail: Implement the spell/ability stack with LIFO resolution and priority passing.

  - File: `SilverquiLLM-bench/engine/stack.py`
  - `StackObject`: dataclass holding `source` (card or ability ref), `controller: Player`, `targets: list`, `on_resolve: Callable`, `is_mana_ability: bool = False`.
  - `Stack`:
    - Internal: `list[StackObject]` (last = top).
    - Methods: `push(obj)`, `pop() -> StackObject`, `peek() -> StackObject | None`, `is_empty() -> bool`, `objects() -> list` (top to bottom).
  - `priority_loop(game: GameState)`:
    - Active player gets priority. May play spells/abilities (push to stack) or pass.
    - After active player passes, non-active player gets priority.
    - If both pass in succession with stack non-empty, resolve top of stack (pop, call `on_resolve(game)`), then run `check_state_based_actions(game)`, then active player gets priority again.
    - If both pass with stack empty, proceed to next phase/step.
    - Player decisions come from `Player.choose()` — DeterministicPlayer's script drives this.
  - Mana abilities resolve immediately (don't use the stack).
  - Testability: push two objects, resolve them, verify LIFO order. Test priority passing with DeterministicPlayer scripts.
- [ ] **State-based actions**
  Detail: Implement the SBA checker that runs after each stack resolution and at other key points.

  - File: `SilverquiLLM-bench/engine/state_based_actions.py`
  - `check_state_based_actions(game: GameState) -> bool` — returns True if any action was taken (must be called repeatedly until stable).
  - SBAs to implement:
    - Player with 0 or less life loses.
    - Creature with toughness 0 or less → graveyard.
    - Creature with lethal damage marked → destroyed (move to graveyard).
    - Player who drew from empty library loses.
    - Legend rule: if a player controls 2+ legendaries with the same name, they choose one to keep; others go to graveyard.
    - Token not on battlefield → ceases to exist (remove from game).
    - Aura not attached to legal object → graveyard.
    - +1/+1 and -1/-1 counter annihilation.
  - Loop: `resolve_state_based_actions(game)` calls `check_state_based_actions` in a loop until no actions taken, then checks for triggers.
  - Testability: set up creature with 0 toughness → verify moved to graveyard. Player life to 0 → verify loss. Two same-name legendaries → verify legend rule.
- [ ] **Card base classes and CardImpl interface**
  Detail: Implement the base card class hierarchy matching the Card Interface spec.

  - File: `SilverquiLLM-bench/engine/card.py`
  - `GameObject`: base class for anything that can exist in zones. Fields: `object_id: int` (auto-incrementing), `owner: Player`, `controller: Player`.
  - `CardImpl(GameObject)`: Fields: `name`, `mana_cost`, `card_types`, `subtypes`, `supertypes`, `keywords`, `rules_text`. Methods (override in subclasses): `can_cast`, `on_cast`, `on_resolve`, `get_targets`, `register_triggers`, `register_replacement_effects`, `get_activated_abilities`, `get_modes() -> list[Mode]` (empty default for non-modal cards).
  - Subclasses:
    - `Creature(CardImpl)` — `base_power`, `base_toughness`, `power`/`toughness` properties (with modification support), `damage_marked`, `is_tapped`, `summoning_sick`, combat flags.
    - `Instant(CardImpl)`, `Sorcery(CardImpl)` — no extra fields.
    - `Enchantment(CardImpl)` — `attached_to` for auras, `apply_continuous_effect()`, `on_enchant()`, `on_detach()`.
    - `Artifact(CardImpl)`, `ArtifactCreature(Creature)`.
    - `Planeswalker(CardImpl)` — `starting_loyalty`, `loyalty`, `get_loyalty_abilities()`.
    - `Land(CardImpl)` — override `can_cast` to check land play limits, `get_mana_abilities()`.
  - Supporting dataclasses: `ActivatedAbility`, `LoyaltyAbility`, `ManaAbility`, `ContinuousEffect`, `Mode`.
  - Testability: instantiate a vanilla Creature, verify power/toughness, cmc, keywords. Instantiate a Land, verify it's not castable via mana.
- [ ] **Casting and resolution pipeline**
  Detail: Wire up the full flow from casting a spell to resolution.

  - File: `SilverquiLLM-bench/engine/casting.py`
  - `cast_spell(game, player, card)`: verify `can_cast` → move hand to stack → choose targets → pay costs → call `on_cast` → push StackObject.
  - Resolution (called by stack pop): call `on_resolve` → permanents to battlefield, instants/sorceries to graveyard.
  - `play_land(game, player, land_card)`: verify land play remaining → move hand to battlefield → decrement `land_plays_remaining`.
  - Timing checks: sorcery-speed = main phase + empty stack + active player. Instant-speed or flash = any priority.
  - Testability: cast a vanilla creature → verify battlefield. Cast an instant → verify graveyard. Attempt sorcery at instant speed → verify rejection.
- [ ] **Triggered abilities system**
  Detail: Implement the event-driven trigger registration and firing mechanism.

  - File: `SilverquiLLM-bench/engine/triggers.py`
  - `EventType` enum: ENTERS_BATTLEFIELD, LEAVES_BATTLEFIELD, DEALS_DAMAGE, LOSES_LIFE, GAINS_LIFE, DRAWS_CARD, BEGINNING_OF_UPKEEP, BEGINNING_OF_COMBAT, END_OF_TURN, CREATURE_DIES, SPELL_CAST, ATTACKS, BLOCKS, etc.
  - `TriggerRegistration`: dataclass with `event_type`, `condition`, `effect`, `source`, `controller`.
  - `TriggerManager`: `register(trigger)`, `unregister(source)`, `fire_event(game, event_type, data)` — checks conditions, pushes matching triggers onto stack. APNAP ordering for different players.
  - Integration: call `card.register_triggers(game)` when entering battlefield, `unregister` on leave.
  - Testability: card with ETB trigger → move to battlefield → fire event → verify StackObject pushed.
- [ ] **Activated abilities system**
  Detail: Implement activated abilities that go on the stack (or resolve immediately for mana abilities).

  - File: `SilverquiLLM-bench/engine/abilities.py`
  - `activate_ability(game, player, ability)`: verify timing → pay costs → if mana ability: resolve immediately; else: push to stack.
  - Tap symbol: cost function checks `not source.is_tapped` and sets `source.is_tapped = True`.
  - `LoyaltyAbility` — cost is loyalty adjustment, once-per-turn restriction.
  - Testability: tap-for-mana on a land → verify mana added and card tapped. Non-mana activated ability → verify it goes on stack.
- [ ] **Combat system**
  Detail: Implement declare attackers → declare blockers → damage → end combat.

  - File: `SilverquiLLM-bench/engine/combat.py`
  - `CombatState`: tracks attackers, blockers, damage assignment.
  - `declare_attackers_step(game)`: active player chooses attackers via `Player.choose()`. Tap attackers (unless vigilance). Check summoning sickness/haste, defender.
  - `declare_blockers_step(game)`: defending player assigns blockers. Menace check (2+ blockers required). Flying/reach check. Controller orders blockers for damage assignment.
  - `combat_damage_step(game)`: first strike damage → SBAs → normal damage. Handle trample (excess over blocker toughness → defending player), lifelink, deathtouch. Unblocked → damage to player.
  - `end_combat_step(game)`: remove from combat, clear combat state.
  - Testability: attack/block scenario → verify damage, trample overflow, first strike ordering, lifelink life gain.
- [ ] **Continuous effects and layer system**
  Detail: Implement the 7-layer system for continuous effects.

  - File: `SilverquiLLM-bench/engine/continuous_effects.py`
  - `Layer` enum: COPY (1), CONTROL (2), TEXT (3), TYPE (4), COLOR (5), ABILITY (6), POWER_TOUGHNESS (7). Layer 7 sub-layers: 7a (characteristic-defining), 7b (set P/T), 7c (modify P/T), 7d (counters).
  - `ContinuousEffect`: dataclass with `source`, `layer`, `sublayer`, `apply` callable, `timestamp`, `duration`.
  - `EffectManager`: `add(effect)`, `remove_expired(game)`, `apply_all(game)` — apply in layer order, timestamp within layer.
  - Phase 1 scope: implement layers 4 (type-changing), 6 (ability granting/removing), and 7c/7d (P/T mods and counters). Layers 1-3 and 5 can be stubs.
  - Testability: +2/+2 effect on a 2/2 → verify reads as 4/4. Test timestamp ordering.
- [ ] **Replacement effects engine**
  Detail: Implement the replacement effect system (separate from triggers per spec).

  - File: `SilverquiLLM-bench/engine/replacement_effects.py`
  - `ReplacementEffect`: dataclass with `event_type: str`, `source`, `condition`, `replacement` callable.
  - `ReplacementManager`: `register(effect)`, `unregister(source)`, `apply(game, event_type, event_data) -> modified event_data`. If multiple replacements apply to same event, affected player chooses order.
  - Key difference from triggers: no stack, modifies event in-place, "instead" semantics.
  - Integration: `card.register_replacement_effects(game)` called when entering battlefield.
  - Phase 1 scope: basic infrastructure. Most Foundations cards won't use replacement effects, but the mechanism must exist for CardImpl's `register_replacement_effects` method.
  - Testability: register a "if creature would die, exile instead" replacement → verify creature goes to exile, not graveyard.
- [ ] **Game setup, helper actions, and the full game loop**
  Detail: Wire everything together: game initialization, common actions, main loop.

  - File: `SilverquiLLM-bench/engine/game.py`
  - `create_game(player1, player2, deck1, deck2) -> GameState`: set life to 20, place decks in libraries, shuffle, draw 7 each, set active player.
  - Common actions on GameState: `deal_damage`, `destroy`, `sacrifice`, `exile`, `draw_card`, `discard`, `create_token`, `add_counter`, `remove_counter`, `tap`, `untap`.
  - `run_game(game) -> Player | None`: loop `run_turn` until `is_game_over`. Return winner.
  - Testability: create game with two players and simple decks, run one full turn, verify phase progression and card draw.
- [ ] **test_utils module for engine validation**
  Detail: Implement the test helper API that benchmark agents will also use in Phase 2.

  - File: `SilverquiLLM-bench/tests/test_utils.py`
  - Functions:
    - `create_game(deck1, deck2, ...) -> GameState` — convenience wrapper, accepts card names via registry.
    - `set_board_state(game, player_index, battlefield=[], hand=[], graveyard=[], life=None, mana=None)` — directly set zones for test setup.
    - `cast_spell(game, player_index, card_name, targets=None)` — find card in hand, cast, pass priority until resolved.
    - `advance_to_phase(game, phase, step=None)` — fast-forward game state, passing priority automatically.
    - `declare_attackers(game, attacker_names)` — advance to combat, declare attackers.
    - `declare_blockers(game, assignments)` — `{"attacker": ["blocker1", ...]}`.
  - Each function raises descriptive errors on failure.
  - Testability: meta-test using test_utils to set up a board and cast a spell.
- [ ] **Card registry and Scryfall data pipeline**
  Detail: Build card data fetcher and registry mapping names to implementations.

  - File: `SilverquiLLM-bench/cards/registry.py`
  - `CardRegistry`: `register(name, impl_class, metadata)`, `get(name)`, `create_instance(name, owner)`, `list_all()`.
  - File: `SilverquiLLM-bench/cards/scryfall.py`
  - `fetch_set(set_code) -> list[CardMetadata]` — fetch from Scryfall API, paginate, cache to `data/sets/{code}.json`.
  - `CardMetadata`: dataclass with `name, mana_cost_str, type_line, oracle_text, power, toughness, colors, keywords, rarity, set_code, collector_number`.
  - Fetch MTG Foundations (set code: `fdn`).
  - Testability: mock Scryfall response, verify parsing. Test registry round-trip.
- [ ] **Basic land implementations (Plains, Island, Swamp, Mountain, Forest)**
  Detail: Implement the 5 basic lands as the simplest card implementations.

  - File: `SilverquiLLM-bench/cards/foundations/basic_lands.py`
  - Each subclasses `Land`. Supertypes = `{BASIC}`. Subtypes = land type.
  - Each has a `ManaAbility` that taps to produce 1 mana of its color.
  - Register all 5 via `register_basic_lands(registry)`.
  - Testability: play a Plains, tap it, verify 1 white mana in pool. Verify can't play a second land same turn.
- [ ] **Vanilla and French vanilla creatures from Foundations (~15 cards)**
  Detail: Implement simple creatures covering keyword variety. Verify exact card names against Scryfall data from the pipeline.

  - File: `SilverquiLLM-bench/cards/foundations/simple_creatures.py`
  - Targets (verify names against fetched Foundations data):
    - Vanilla: `Grizzly Bears` (2/2 for {1}{G}), `Glory Seeker` (2/1 for {1}{W}), similar.
    - French vanilla: `Serra Angel` (4/4 flying vigilance), `Air Elemental` (4/4 flying), `Giant Spider` (2/4 reach), `Child of Night` (2/1 lifelink), etc.
  - Consider a generic factory: `make_vanilla(name, cost, power, toughness, keywords)` for pure stat creatures.
  - Register all in registry.
  - Testability: for each, test casting and battlefield presence with correct P/T and keywords. Test flying/reach blocking rules in combat.
- [ ] **Simple instants and sorceries from Foundations (~10 cards)**
  Detail: Implement non-creature spells to validate casting and resolution.

  - File: `SilverquiLLM-bench/cards/foundations/simple_spells.py`
  - Targets (verify against Foundations set):
    - Damage: `Lightning Bolt` (3 damage to any target), `Lava Axe` (5 to player).
    - Buff: `Giant Growth` (+3/+3 until EOT — continuous effect, layer 7c).
    - Draw: `Divination` (draw 2).
    - Removal: `Murder` (destroy target creature).
    - Counter: `Negate` (counter noncreature), `Cancel` (counter any spell).
    - Utility: `Naturalize` (destroy artifact/enchantment), `Mind Rot` (discard 2), `Raise Dead` (graveyard to hand).
  - Each overrides `get_targets()` and `on_resolve()`.
  - Counter spells remove target from stack → graveyard.
  - Testability: Lightning Bolt a 3/3 → verify dies. Giant Growth → verify +3/+3 and EOT revert. Negate a Divination → verify countered.
- [ ] **Simple enchantments and artifacts from Foundations (~5 cards)**
  Detail: Implement permanent noncreature spells to validate aura/artifact handling.

  - File: `SilverquiLLM-bench/cards/foundations/simple_permanents.py`
  - Targets (verify against Foundations set):
    - Aura buff: `Holy Strength` or `Oakenform` type (+P/+T, layer 7c).
    - Aura debuff: `Pacifism` (can't attack or block — layer 6, removes attack/block ability).
    - Mana rock: `Sol Ring` or equivalent (tap: add {C}{C}).
  - Aura implementation: `attached_to` field. On resolve, attach to target. SBAs handle aura without legal target → graveyard.
  - Testability: enchant creature with Pacifism → verify can't declare as attacker. Destroy enchanted creature → verify aura goes to graveyard.
- [ ] **End-of-turn cleanup and damage clearing**
  Detail: Ensure the cleanup step correctly resets transient state.

  - Integrate into `SilverquiLLM-bench/engine/turn.py` and `continuous_effects.py`.
  - Cleanup step:
    1. Active player discards to hand size (max 7) via `Player.choose_card`.
    2. Remove all "until end of turn" continuous effects.
    3. Clear damage marked on all creatures.
    4. Clear combat flags.
    5. Empty mana pools.
    6. Check SBAs.
    7. If triggers fired during cleanup, process them and do another cleanup step.
  - Testability: Giant Growth a creature → advance to cleanup → verify P/T reverts. Deal 2 damage to 3/3 → cleanup → verify damage cleared.
- [ ] **Integration test: multi-turn game with Foundations cards**
  Detail: End-to-end test playing out 5+ turns using DeterministicPlayer and Foundations cards.

  - File: `SilverquiLLM-bench/tests/test_integration.py`
  - Example scenario:
    1. P1: Plains, Forests, Grizzly Bears, Serra Angel, Giant Growth.
    2. P2: Islands, Mountains, Lightning Bolt, Air Elemental, Cancel.
    3. Script turns: land drops, creature casts, removal, counterspells, combat, damage.
    4. Assert at each step: life totals, battlefield state, graveyard contents, hand sizes.
  - Validates: mana, casting, stack, priority, combat, counters, triggers, SBAs, cleanup all working together.
  - This test is the "smoke test" that proves Phase 1 engine is functional.
---

**Note:** This covers the engine + ~35 representative Foundations cards. Porting the remaining ~225 Foundations cards will be a follow-up TODO once the engine is validated. Card names above should be verified against the Scryfall data fetched by the pipeline item.
