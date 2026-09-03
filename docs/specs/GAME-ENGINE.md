Status: SETTLED

Last updated: 2026-04-28

# Game Engine

Python port of XMage's rules engine with MTG Foundations as the base set.

## Context

XMage is the reference open-source Java implementation (28,000+ cards, battle-tested rules). Porting to Python preserves correctness while gaining LLM-friendliness and simpler benchmark integration.

## Design

### Porting Strategy

Source: `github.com/magefree/mage` (Java, MIT — license-compatible with SilverquiLLM-bench, which is likewise MIT)

**What to port:**

- Core rules engine — game loop, stack, priority, combat, state-based actions, continuous effects, zones
- Card framework — base classes and ability infrastructure
- MTG Foundations cards — the fixed 301-card Base Set pool (see Base Set below)
**How to port:**

- Preserve XMage's class hierarchy; translate to Pythonic idioms (snake_case, dataclasses, type hints). Requires Python ≥3.12. All project config (`pyproject.toml`, `ruff.toml`) must target 3.12.
- 1:1 logic mapping — each XMage Java method gets a corresponding Python method
- Tests alongside port — verify each subsystem and card matches XMage behavior
- Base-set validation via Replay Validation — engine correctness is checked by replaying 17lands MTGA game data against game-state checkpoints, rather than XMage differential testing (MTGA is closer to ground truth and avoids cross-language comparison complexity)
- Incremental — port in dependency order: zones → mana → stack → combat → triggers → continuous effects → cards
### Core Systems

**Turn Structure**: Full MTG turn (untap → upkeep → draw → main 1 → combat → main 2 → end → cleanup). Priority passes at appropriate points.

**Mana System**: 5 colors + colorless + generic. Mana abilities resolve immediately. Supports hybrid, Phyrexian, and X costs. When explicit `choices` are provided, generic mana is deducted from the pool before `_solve_hybrid()` runs, so the solver cannot steal reserved mana (grilling 2026-05-10). Cost-reduction hooks need the controller: `get_cost_reduction()` temporarily sets `card.controller` before calling the hook and restores it afterward, and `cast_spell()` sets the controller early for the same reason (grilling 2026-05-10).

**The Stack**: LIFO resolution. Priority passing before each resolution. State-based actions checked after each resolution.

**Combat**: Attacker/blocker declaration with legality checks, damage assignment order, first/double strike, trample, combat triggers.

**Triggered Abilities**: Event-driven system. Engine emits events; cards register listeners. Triggers go on the stack. Supports: ETB, LTB, dies, deals damage, phase triggers, cast triggers, state change triggers. Self-ETB effects run directly in `on_resolve()` rather than as triggers, because `register_triggers()` fires after the ETB event and self-ETB triggers would never match during normal resolution (e.g. Embercleave auto-attach) (grilling 2026-05-10).

**Activated Abilities**: Cost → effect pattern. Timing restrictions (sorcery vs instant speed). Goes on stack (except mana abilities).

**Zones**: Battlefield, hand, library, graveyard, exile, stack, command zone. Zone transitions emit events.

**State-Based Actions**: Checked when a player would receive priority. Lethal damage/toughness, 0 life, legend rule, counter cancellation, aura/equipment legality.

**Continuous Effects & Layers**: 7-layer system (copy → control → text → type → color → ability → P/T). Timestamp ordering within layers. Equipment and aura P/T bonuses apply in Layer 7 `SubLayer.MODIFY_PT` (7c) while keywords apply in Layer 6, preventing CDAs (Layer 7a) from overwriting P/T bonuses; protection is a continuous effect reapplied on each layer pass — cleared during `_reset_characteristics()` rather than stored as a sticky attribute (grilling 2026-05-10).

### Base Set: MTG Foundations Draft Set

The Base Set is the primary reference set agents can browse during benchmarking: a fixed pool of **301 limited-format cards — FDN 001–291 plus SPG 074–083 Special Guests** — a direct XMage port of the MTG Foundations Draft Set, sourced from Scryfall/MTGJson. The pool is fixed: there is no Expanded Pool of extra reference cards, and none is planned. Agents implement new mechanics from scratch using oracle text plus the comprehensive rules, with no curated reference implementations for target-set mechanics.

The Base Set serves as:

1. Engine validation — validated via Replay Validation against 17lands data; all Foundations tests passing = core mechanics correct
2. Agent reference — agents browse these as working examples during benchmarking
3. Regression suite — catches engine regressions

### Game State API (Draft)

```python
class GameState:
    players: list[Player]
    active_player: Player
    priority_player: Player
    phase: Phase
    stack: Stack
    turn_number: int

    def get_battlefield(self, player=None) -> list[Permanent]: ...
    def get_hand(self, player) -> list[Card]: ...
    def get_graveyard(self, player) -> list[Card]: ...
    def get_library(self, player) -> list[Card]: ...
    def get_exile(self) -> list[Card]: ...
    def deal_damage(self, source, target, amount): ...
    def move_zone(self, card, from_zone, to_zone): ...
    def add_mana(self, player, mana): ...
    def pay_cost(self, player, cost) -> bool: ...
    def create_token(self, controller, token_def) -> Permanent: ...
    def add_counter(self, permanent, counter_type, count=1): ...
    def remove_counter(self, permanent, counter_type, count=1): ...
    def tap(self, permanent): ...
    def untap(self, permanent): ...
    def destroy(self, permanent): ...
    def sacrifice(self, player, permanent): ...
    def exile(self, card): ...
    def draw_card(self, player, count=1): ...
    def discard(self, player, card): ...
```

Method signatures will be refined during implementation.

### Player Decision Interface

```python
class Player(ABC):
    @abstractmethod
    def choose_target(self, game, source, targets, requirement) -> Any: ...
    @abstractmethod
    def choose(self, game, choices, message) -> str: ...
    @abstractmethod
    def choose_yes_no(self, game, message) -> bool: ...
    @abstractmethod
    def assign_damage_order(self, game, blockers) -> list[Permanent]: ...
    @abstractmethod
    def choose_card(self, game, cards, message) -> Card: ...
```

All tests use `DeterministicPlayer` with scripted actions (set up → act → assert), against pre-determined board states. No AI decision-making in v1; an AI `StrategyPlayer` is deferred.

```python
player = DeterministicPlayer(
    actions=[
        CastSpell("Lightning Bolt", target="Grizzly Bears"),
        PassPriority(),
    ]
)
```

### Engine Extensibility by Agents

During benchmark runs, the engine is **writable** — agents may add new mechanics, modify existing systems, or extend the class hierarchy to implement cards that require features not yet in the base engine.

**Design principles for extensibility:**

- The engine's architecture (hooks, events, layers) should be expressive enough that most mechanics can be implemented by adding new code rather than modifying core systems
- Agents see `engine_api.md` and can browse the full `engine/` source in their workspace
- Engine changes persist throughout a single benchmark run — the agent manages a writable engine copy inside the container (see [AGENT-CONTAINERS.md](AGENT-CONTAINERS.md))
- All evaluation is post-run: after the agent finishes, the evaluator runs all cards' tests against the final engine state
- The base engine (from the repo) is the starting point for every run — different agents start from the same baseline
**What agents typically extend:**

- New keyword abilities (e.g., Ward, Magecraft) as new classes/modules
- New ability types or effect patterns
- New zone interactions (e.g., exile-to-hand mechanics)
- Helper utilities for common patterns
**What agents should NOT break:**

- Core game loop and priority system
- Existing card implementations (Foundations cards)
- Test utilities and DeterministicPlayer interface
- Zone, mana, and stack fundamentals
### Out of Scope (v1)

Multiplayer, sideboard/best-of-three, companion/partner, dungeons/Ring, day/night, voting, ante. Architecture supports these via XMage; just not ported for v1.

## Oracle Workspace Engine Extensions

Engine primitives and mechanic implementations added to the **Test Oracle Workspace** engine (`benchmarks/sos/data/test_oracle_workspace/engine/`) to support SOS Test Oracle Impls. These are additive extensions to the oracle's 1:1 mirror of the canonical engine; they document how specific SOS mechanics are modeled for reference. *(Drained from ****`KEY_DECISIONS.md`****, 2026-05-30.)*

### Resolution & the stack

- **Spell→graveyard replacement effect**: `_resolve_spell` in `engine/casting.py` fires a `_SpellToGraveyardReplacementEvent` and consults the `ReplacementManager` before moving an instant/sorcery to the graveyard; the replacement's `destination` decides the actual zone. Enables exile-on-resolution cards (sos_1).
- **All-targets-illegal = countered on resolution (CR 608.2b)**: if every target is illegal at resolution the spell is countered and no effects happen — including untargeted bonus effects (e.g. life gain). Untargeted effects resolve only if at least one target remains legal.
- **Spell copies cease to exist (CR 707.2)**: Casualty copies use `copy.copy(card)`; the copy's `on_resolve` runs the effect but performs no zone movement — copies are not cards and vanish after resolving (`_handle_casualty()`).
### Casting pipeline

- **`cast_spell_for_cost`**** mirrors the full pipeline**: target selection, `on_cast()`, stack push with the proper `on_resolve` closure, and passing `stack_obj` to `_resolve_spell` — substituting only the mana cost (miracle). Skipping any step breaks spells with targets or cast-time hooks.
- **Casualty hook wired into all casting entry points**: `_handle_casualty()` runs after the stack push in `cast_spell()`, `cast_spell_for_cost()`, and `cast_spell_free()`, so any instant/sorcery cast offers casualty while a granter is on the battlefield.
- **Restricted mana primitive**: `ManaPool.add_restricted(amount, color, restriction)` + `_check_restricted_mana()` validate at cast time — if unrestricted mana can't cover the cost, restricted mana must be used and the spell must match the restriction (else `CastingError`). General primitive; first user sos_257 (instant/sorcery-only mana).
- **Affinity**: `Keyword.AFFINITY` added for inspection only; reduction logic stays in `cost_reduction(game)` via the battlefield-scan grant pattern. Multiple affinity granters stack — `get_cost_reduction()` multiplies creature count by granter count.
### Triggers & timing

- **Attack-trigger targeting locks in via the condition callback** (closest hook to "ability goes on stack"); single-target triggers auto-select to avoid consuming a script entry.
- **Miracle trigger tracks ****`event.card`**: a closure variable (`_miracle_drawn_card`) shared between the condition and effect captures the drawn card, so the correct card is offered even if the hand changes (sos_201).
- **`cards_drawn_this_turn`**** resets at turn start**: `advance_phase()` zeroes `active_player.cards_drawn_this_turn` at the new-turn wrap-around (needed for "first card drawn each turn").
### Permanents & state-based actions

- **Planeswalker damage removes loyalty**: `deal_damage()` in `engine/game.py` detects planeswalkers via `hasattr(target, "loyalty")`; check order is player → planeswalker → creature.
- **Planeswalker 0-loyalty SBA (CR 704.5i)**: `check_state_based_actions()` puts a 0-loyalty planeswalker into its owner's graveyard.
- **Persistent animation survives cleanup**: cards with persistent animation override `_reset_characteristics()` to re-apply the creature type after the base reset when `_is_animated` is true; only the temporary P/T boost reverts at end of turn.
- **Lifecycle hooks wired globally**: `move_to_zone()` calls `on_leave_battlefield(game)` when a card leaves the battlefield; `_do_cleanup_step()` calls `end_of_turn_cleanup()` on all battlefield permanents.
### Mechanics

- **Surveil uses scripted choices**: surveil N consults the player's scripted choices to decide keep-on-top vs to-graveyard per card, rather than always milling.
- **Paradigm = self-exile replacement + recurring cast trigger**: self-exile reuses the `ReplacementManager` / `_SpellToGraveyardReplacementEvent` mechanism; a recurring "may cast from exile" trigger fires from `BeginningOfMainPhaseEvent` wired into `advance_phase()`, casting via `cast_spell_free` (sos_120).

## Relevant ADRs

| ADR | Decision |
|---|---|
| [ADR-010](../adr/ADR-010-test-oracle-workspace-uses-independent-engine.md) | Test Oracle Workspace Uses Independent Engine |
