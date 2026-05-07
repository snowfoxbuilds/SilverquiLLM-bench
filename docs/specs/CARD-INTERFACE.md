Status: SETTLED

Last updated: 2026-04-28

# Card Interface

Python class interface that LLMs must implement for each MTG card.

## Context

The card interface is the primary contract between the game engine and LLM-generated code. One file per card, one class per card, subclassing a type-specific base class.

## Design

### Base Card Class

```python
class Card:
    name: str
    mana_cost: str                     # e.g. "{2}{W}{U}"
    card_types: list[str]
    subtypes: list[str]
    supertypes: list[str]
    keywords: list[str]
    rules_text: str

    def can_cast(self, game: GameState, player: Player) -> bool: ...
    def on_cast(self, game: GameState, player: Player, targets: list) -> None: ...
    def on_resolve(self, game: GameState, player: Player, targets: list) -> None: ...
    def get_targets(self, game: GameState, player: Player) -> TargetRequirement | None: ...
    def register_triggers(self, game: GameState, permanent: Permanent) -> None: ...
    def register_replacement_effects(self, game: GameState, permanent: Permanent) -> None: ...
    def get_activated_abilities(self) -> list[ActivatedAbility]: ...
```

### Type-Specific Subclasses

| Subclass | Additional Attributes | Key Methods |
| --- | --- | --- |
| `Creature` | `power`, `toughness` | `modify_power()`, `modify_toughness()`, `can_attack()`, `can_block()`, `on_deals_damage()`, `on_death()` |
| `Instant` | — | All logic in `on_resolve()` |
| `Sorcery` | — | Like Instant, sorcery speed only |
| `Enchantment` | — | `apply_continuous_effect()`, `on_enchant()`, `on_detach()` |
| `Artifact` | — | Similar to Enchantment, may have activated abilities |
| `ArtifactCreature` | Inherits both | Dual creature + artifact behavior |
| `Planeswalker` | `starting_loyalty` | `get_loyalty_abilities()` |
| `Land` | — | `get_mana_abilities()` (played, not cast) |

### Supporting Types

```python
@dataclass
class TargetRequirement:
    count: int | range
    filter: Callable[[GameState, Any], bool]
    zone: Zone = Zone.BATTLEFIELD
    description: str = ""

@dataclass
class ActivatedAbility:
    cost: Cost
    effect: Callable[[GameState, Player, list], None]
    timing: Timing = Timing.INSTANT
    targets: TargetRequirement | None = None

@dataclass
class LoyaltyAbility:
    loyalty_cost: int
    effect: Callable[[GameState, Player, list], None]
    targets: TargetRequirement | None = None

@dataclass
class ManaAbility:
    cost: Cost
    mana_produced: str

@dataclass
class ContinuousEffect:
    layer: int                          # 1-7
    apply: Callable[[GameState], None]
    condition: Callable[[GameState], bool] | None = None

@dataclass
class Mode:
    description: str
    targets: TargetRequirement | None
    effect: Callable[[GameState, Player, list], None]
```

### Modal Spells

Modal spells use declarative `get_modes()`. Mode selection handled by `Player` interface; tests use `DeterministicPlayer(actions=[CastSpell(..., mode=0)])`.

```python
def get_modes(self) -> list[Mode]:
    return [
        Mode(
            description="Exile target creature",
            targets=TargetRequirement(count=1, filter=lambda g, t: t.is_creature()),
            effect=lambda g, p, t: g.exile(t[0]),
        ),
        Mode(
            description="Draw two cards",
            targets=None,
            effect=lambda g, p, t: g.draw_card(p, 2),
        ),
    ]
```

### Replacement Effects

Replacement effects modify events before they happen (no stack). Separate from triggers via `register_replacement_effects()`:

```python
def register_replacement_effects(self, game, permanent):
    game.register_replacement(
        event="creature_dies",
        source=permanent,
        condition=lambda e: True,
        replacement=lambda e: game.exile(e.card),
    )
```

Key differences from triggers: no stack, in-place event modification, "instead" semantics, one replacement per event (affected player chooses if multiple apply).

### Example: Vanilla Creature

```python
class GrizzlyBears(Creature):
    name = "Grizzly Bears"
    mana_cost = "{1}{G}"
    card_types = ["Creature"]
    subtypes = ["Bear"]
    supertypes = []
    keywords = []
    rules_text = ""
    power = 2
    toughness = 2
```

### Example: ETB Trigger

```python
class MultanisAcolyte(Creature):
    name = "Multani's Acolyte"
    mana_cost = "{G}{G}"
    card_types = ["Creature"]
    subtypes = ["Elf"]
    keywords = ["Echo"]
    rules_text = "When Multani's Acolyte enters the battlefield, draw a card."
    power = 2
    toughness = 1

    def register_triggers(self, game, permanent):
        game.register_trigger(
            event="enters_battlefield",
            source=permanent,
            condition=lambda e: e.permanent == permanent,
            effect=lambda e: game.draw_card(permanent.controller),
        )
```

### New Mechanics Declaration

Target set cards may use mechanics not found in the Foundations card pool. When an agent's implementation requires a mechanic that has no example in `foundations/`, it should declare this in a `mechanics_declaration.json` file in the workspace:

```json
{
  "new_mechanics": [
    {
      "name": "Ward",
      "rules_reference": "702.21",
      "description": "Whenever this permanent becomes the target of a spell or ability an opponent controls, counter that spell or ability unless its controller pays the ward cost.",
      "implementation_approach": "Registered as a trigger on 'becomes_target' event. Checks if source controller is an opponent, then creates a pay-or-counter choice.",
      "engine_hooks_used": ["register_triggers", "counter_spell", "pay_cost"],
      "foundation_analogs": ["Hexproof (similar targeting restriction)", "Counterspell (counter mechanic)"]
    },
    {
      "name": "Magecraft",
      "rules_reference": null,
      "description": "Whenever you cast or copy an instant or sorcery spell, [effect].",
      "implementation_approach": "Trigger on 'spell_cast' event filtered to instant/sorcery types, plus 'spell_copied' event.",
      "engine_hooks_used": ["register_triggers"],
      "foundation_analogs": ["Prowess (triggers on instant/sorcery cast)"]
    }
  ]
}
```

**Schema fields per mechanic:**

- `name`: Mechanic keyword or ability word
- `rules_reference`: MTG comprehensive rules section number (if known, from rules lookup skill)
- `description`: Plain English description of the mechanic
- `implementation_approach`: How the agent plans to implement it using the engine API
- `engine_hooks_used`: Which `Card` methods or `GameState` methods the implementation relies on
- `foundation_analogs`: Existing Foundations cards with similar (but not identical) patterns the agent used as reference
This declaration serves two purposes:

1. **Postmortem analysis** — Reviewers can check whether the agent correctly understood the mechanic and chose appropriate engine hooks
2. **Engine gap detection** — If many agents flag the same mechanic as lacking engine support, it surfaces a gap to fix
The file is optional. Agents are instructed to create it when they encounter mechanics with no direct example in `foundations/`, but the runner does not enforce it.

## Decisions

- **Declarative properties + hook methods**: Static card data as class attributes; behavior via method overrides. [SETTLED]
- **One file, one class per card**: Standardized class name from `template.py` for cross-evaluation compatibility. [SETTLED]
- **Modal spells via get_modes()**: All modes available; DeterministicPlayer selects mode in tests. [SETTLED]
- **Replacement effects separate from triggers**: `register_replacement_effects()` mechanism, no stack, "instead" semantics. [SETTLED]
- **New mechanics declaration**: Agents produce `mechanics_declaration.json` when using mechanics not in Foundations, documenting approach and engine hooks. [SETTLED]
