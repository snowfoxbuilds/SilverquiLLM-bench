Status: SETTLED

Last updated: 2026-04-28

# Game Engine

Python port of XMage's rules engine with MTG Foundations as the base set.

## Context

XMage is the reference open-source Java implementation (28,000+ cards, battle-tested rules). Porting to Python preserves correctness while gaining LLM-friendliness and simpler benchmark integration.

## Design

### Porting Strategy

Source: `github.com/magefree/mage` (Java, MIT)

**What to port:**

- Core rules engine — game loop, stack, priority, combat, state-based actions, continuous effects, zones
- Card framework — base classes and ability infrastructure
- MTG Foundations cards — ~260 cards as the base set
**How to port:**

- Preserve XMage's class hierarchy; translate to Pythonic idioms (snake_case, dataclasses, type hints). Requires Python ≥3.12. All project config (`pyproject.toml`, `ruff.toml`) must target 3.12.
- 1:1 logic mapping — each XMage Java method gets a corresponding Python method
- Tests alongside port — verify each subsystem and card matches XMage behavior
- Incremental — port in dependency order: zones → mana → stack → combat → triggers → continuous effects → cards
### Core Systems

**Turn Structure**: Full MTG turn (untap → upkeep → draw → main 1 → combat → main 2 → end → cleanup). Priority passes at appropriate points.

**Mana System**: 5 colors + colorless + generic. Mana abilities resolve immediately. Supports hybrid, Phyrexian, and X costs.

**The Stack**: LIFO resolution. Priority passing before each resolution. State-based actions checked after each resolution.

**Combat**: Attacker/blocker declaration with legality checks, damage assignment order, first/double strike, trample, combat triggers.

**Triggered Abilities**: Event-driven system. Engine emits events; cards register listeners. Triggers go on the stack. Supports: ETB, LTB, dies, deals damage, phase triggers, cast triggers, state change triggers.

**Activated Abilities**: Cost → effect pattern. Timing restrictions (sorcery vs instant speed). Goes on stack (except mana abilities).

**Zones**: Battlefield, hand, library, graveyard, exile, stack, command zone. Zone transitions emit events.

**State-Based Actions**: Checked when a player would receive priority. Lethal damage/toughness, 0 life, legend rule, counter cancellation, aura/equipment legality.

**Continuous Effects & Layers**: 7-layer system (copy → control → text → type → color → ability → P/T). Timestamp ordering within layers.

### Base Set: MTG Foundations (Expanded)

The Foundations card pool is the primary reference set that agents can browse during benchmarking. The initial target is ~260 cards from the MTG Foundations set, but the pool should be **expanded beyond vanilla Foundations** to ensure agents have working examples of diverse mechanics they'll encounter in target sets.

**Core pool (FDN 001–291, limited format cards):** Direct XMage port of MTG Foundations limited format pool. Serves as:

1. Engine validation — all Foundations tests passing = core mechanics correct
2. Agent reference — agents browse these as working examples during benchmarking
3. Regression suite — catches engine regressions
**Expanded pool (deferred to post-base-set):** Add cards from other sets that demonstrate mechanics likely to appear in the target set but absent from Foundations. Scoped after Base Set is complete and validated. For Strixhaven (SOS), candidates include:

- **Ward** — Not in Foundations; add exemplar cards (e.g. Frost Titan, Iridescent Hornbeetle)
- **Magecraft** — Strixhaven-specific; add a few simple magecraft cards as reference
- **Learn/Lesson** — Strixhaven-specific exile-to-hand mechanic
- **Modal double-faced cards (MDFCs)** — Add Zendikar/Strixhaven MDFCs if engine supports them
- **Copy spells** — Storm, Fork-type effects for magecraft interaction testing
- **Exile-matters** — Cards that exile from graveyard, foretell, etc.
The expanded pool is curated per target set. Cards are selected based on the classified card specs: scan the target set's mechanics, identify which ones lack Foundations examples, and add 5-10 exemplar cards per gap from older sets.

**Selection criteria for expanded cards:**

- Must have a working XMage implementation to port from
- Prefer simpler cards that cleanly demonstrate the mechanic
- Avoid cards that require un-ported engine features
- Each expanded card gets the same treatment as Foundations: ported implementation + tests
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

All tests use `DeterministicPlayer` with scripted actions (set up → act → assert). No AI decision-making in v1.

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
- Engine changes persist across cards within a single benchmark run (see [BENCHMARK-RUNNER.md](http://benchmark-runner.md/) → Workspace Model)
- After each card, all previous cards' tests are re-run to detect regressions
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

## Decisions

- **Port XMage, not build from scratch**: XMage's rules logic is the ground truth. [SETTLED]
- **Porting scope: Foundations limited pool + targeted expansions**: Core set is FDN 001–291 (~291 limited format cards). Expanded pool deferred until base set is complete and validated via Replay Validation. [UPDATED]
- **Base set validated via Replay Validation**: Engine correctness verified by replaying 17lands MTGA game data and checking game-state checkpoints. Replaces XMage differential testing — MTGA is closer to ground truth and avoids cross-language comparison complexity. [SETTLED]
- **MIT license**: SilverquiLLM-bench and XMage are both MIT licensed. [SETTLED]
- **DeterministicPlayer only for v1**: Pre-determined board states, no AI player. StrategyPlayer deferred. [SETTLED]
- **Foundations card audit deferred to implementation**: Pull card list from Scryfall/MTGJson during Phase 1. [SETTLED]
- **Engine writable during benchmark runs**: Agents may extend the engine to support new mechanics. Changes persist across cards within a run. Regression tested after each card. [SETTLED]
