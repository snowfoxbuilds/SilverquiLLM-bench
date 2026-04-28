Status: SETTLED

Last updated: 2026-04-28

# Game Engine

Python port of XMage's rules engine with MTG Foundations as the base set.

## Context

XMage is the reference open-source Java implementation (28,000+ cards, battle-tested rules). Porting to Python preserves correctness while gaining LLM-friendliness and simpler benchmark integration.

## Design

### Porting Strategy

Source: `github.com/magefree/mage` (Java, GPL-2.0)

**What to port:**

- Core rules engine — game loop, stack, priority, combat, state-based actions, continuous effects, zones
- Card framework — base classes and ability infrastructure
- MTG Foundations cards — ~260 cards as the base set
**How to port:**

- Preserve XMage's class hierarchy; translate to Pythonic idioms (snake_case, dataclasses, type hints). Requires Python ≥3.12.
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

### Base Set: MTG Foundations

~260 cards ported from XMage. Serves as:

1. Engine validation — all Foundations tests passing = core mechanics correct
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

All tests use `DeterministicPlayer` with scripted actions (set up → act → assert). No AI decision-making in v1.

```python
player = DeterministicPlayer(
    actions=[
        CastSpell("Lightning Bolt", target="Grizzly Bears"),
        PassPriority(),
    ]
)
```

### Out of Scope (v1)

Multiplayer, sideboard/best-of-three, companion/partner, dungeons/Ring, day/night, voting, ante. Architecture supports these via XMage; just not ported for v1.

## Decisions

- **Port XMage, not build from scratch**: XMage's rules logic is the ground truth. [SETTLED]
- **Porting scope: Foundations only**: Port exactly as much as needed for MTG Foundations. [SETTLED]
- **GPL-2.0 license**: MagicBench is open source under GPL-2.0. [SETTLED]
- **DeterministicPlayer only for v1**: Pre-determined board states, no AI player. StrategyPlayer deferred. [SETTLED]
- **Foundations card audit deferred to implementation**: Pull card list from Scryfall/MTGJson during Phase 1. [SETTLED]
