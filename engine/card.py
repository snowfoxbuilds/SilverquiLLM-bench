"""Card base classes, CardImpl interface, and supporting dataclasses.

Provides the core class hierarchy for all Magic: The Gathering card types:

- ``GameObject`` — base for anything that can exist in zones.
- ``CardImpl(GameObject)`` — abstract card implementation with hooks for
  casting, resolution, targeting, triggers, and abilities.
- Concrete subclasses: ``Creature``, ``Instant``, ``Sorcery``,
  ``Enchantment``, ``Aura``, ``Artifact``, ``ArtifactCreature``,
  ``Planeswalker``, ``Land``.
- Supporting dataclasses: ``ActivatedAbility``, ``LoyaltyAbility``,
  ``ManaAbility``, ``ContinuousEffect``, ``Mode``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


# ---------------------------------------------------------------------------
# Supporting dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Mode:
    """Represents a single mode of a modal spell or ability.

    Attributes:
        name: Short label for this mode (e.g. ``"Destroy target creature"``).
        description: Detailed rules text for the mode.
    """

    name: str = ""
    description: str = ""


@dataclass
class ActivatedAbility:
    """An activated ability on a permanent.

    Attributes:
        cost: A callable that checks/pays the cost given the game state.
        effect: A callable that applies the effect given the game state.
        description: Human-readable description of the ability.
    """

    cost: Callable[..., Any]
    effect: Callable[..., Any]
    description: str = ""


@dataclass
class LoyaltyAbility:
    """A planeswalker loyalty ability.

    Attributes:
        loyalty_cost: The loyalty cost (positive for ``+``, negative for ``−``).
        effect: A callable that applies the ability's effect.
        description: Human-readable description.
    """

    loyalty_cost: int
    effect: Callable[..., Any]
    description: str = ""


@dataclass
class ManaAbility:
    """A mana ability (does not use the stack).

    Attributes:
        cost: A callable that checks/pays the cost.
        mana_produced: A callable that returns the mana added.
        description: Human-readable description.
    """

    cost: Callable[..., Any]
    mana_produced: Callable[..., Any]
    description: str = ""


@dataclass
class ContinuousEffect:
    """A continuous effect applied by an enchantment or other source.

    Attributes:
        apply: A callable that applies the effect to the game state.
        remove: A callable that removes the effect from the game state.
        description: Human-readable description.
    """

    apply: Callable[..., Any]
    remove: Callable[..., Any]
    description: str = ""


# ---------------------------------------------------------------------------
# GameObject — base class for zone-resident objects
# ---------------------------------------------------------------------------

class GameObject:
    """Base class for anything that can exist in a zone.

    Each instance receives a unique ``object_id`` via a class-level
    auto-incrementing counter.

    Attributes:
        object_id: Unique integer identifier (auto-assigned).
        owner: The player who owns this object.
        controller: The player who currently controls this object.
    """

    _next_id: int = 1

    def __init__(self, owner: Player | None = None, controller: Player | None = None) -> None:
        self.object_id: int = GameObject._next_id
        GameObject._next_id += 1
        self.owner: Player | None = owner
        self.controller: Player | None = controller if controller is not None else owner

    @classmethod
    def reset_id_counter(cls) -> None:
        """Reset the auto-incrementing counter (useful in tests)."""
        cls._next_id = 1


# ---------------------------------------------------------------------------
# CardImpl — abstract card implementation
# ---------------------------------------------------------------------------

class CardImpl(GameObject):
    """Abstract base for all card implementations.

    Subclasses should override the ``can_cast``, ``on_cast``, ``on_resolve``,
    and other hook methods to implement card-specific behaviour.

    Attributes:
        name: Card name.
        mana_cost: The card's mana cost.
        card_types: Set of :class:`~engine.types.CardType` values.
        subtypes: Set of subtype strings (e.g. ``{"Elf", "Warrior"}``).
        supertypes: Set of :class:`~engine.types.Supertype` values.
        keywords: Combination of :class:`~engine.types.Keyword` flags.
        rules_text: The card's rules text string.
    """

    def __init__(
        self,
        name: str = "",
        mana_cost: ManaCost | None = None,
        card_types: set[CardType] | None = None,
        subtypes: set[str] | None = None,
        supertypes: set[Supertype] | None = None,
        keywords: Keyword | None = None,
        rules_text: str = "",
        owner: Player | None = None,
        controller: Player | None = None,
    ) -> None:
        super().__init__(owner=owner, controller=controller)
        self.name: str = name
        self.mana_cost: ManaCost = mana_cost if mana_cost is not None else ManaCost()
        self.card_types: set[CardType] = card_types if card_types is not None else set()
        self.subtypes: set[str] = subtypes if subtypes is not None else set()
        self.supertypes: set[Supertype] = supertypes if supertypes is not None else set()
        self.keywords: Keyword = keywords if keywords is not None else Keyword(0)
        self.rules_text: str = rules_text
        # Snapshot original characteristics for continuous-effect reset.
        self._original_card_types: frozenset[CardType] = frozenset(self.card_types)
        self._original_keywords: Keyword = self.keywords

    # ------------------------------------------------------------------
    # Continuous-effect reset support
    # ------------------------------------------------------------------

    def _reset_characteristics(self) -> None:
        """Reset mutable characteristics to their original (pre-effect) values.

        Called by :meth:`EffectManager.apply_all` before reapplying effects
        so that the recalculation is idempotent.
        """
        self.card_types = set(self._original_card_types)
        self.keywords = self._original_keywords

    # ------------------------------------------------------------------
    # Hook methods — override in subclasses / card definitions
    # ------------------------------------------------------------------

    def can_cast(self, game: GameState) -> bool:
        """Return ``True`` if this card can currently be cast."""
        return True

    def on_cast(self, game: GameState) -> None:
        """Called when the card is cast (before it goes on the stack)."""

    def on_resolve(self, game: GameState) -> None:
        """Called when the spell resolves from the stack."""

    def get_targets(self, game: GameState) -> list[Any]:
        """Return a list of legal targets for this card."""
        return []

    def register_triggers(self, game: GameState) -> None:
        """Register any triggered abilities this card provides."""

    def register_replacement_effects(self, game: GameState) -> None:
        """Register any replacement effects this card provides."""

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return activated abilities this card provides."""
        return []

    def get_modes(self) -> list[Mode]:
        """Return available modes for modal spells/abilities.

        Non-modal cards return an empty list by default.
        """
        return []


# ---------------------------------------------------------------------------
# Creature
# ---------------------------------------------------------------------------

class Creature(CardImpl):
    """A creature card.

    Attributes:
        base_power: The printed power value.
        base_toughness: The printed toughness value.
        damage_marked: Amount of damage currently marked on this creature.
        is_tapped: Whether the creature is tapped.
        summoning_sick: Whether the creature has summoning sickness.
        is_attacking: Combat flag — currently declared as an attacker.
        is_blocking: Combat flag — currently declared as a blocker.
        plus_one_counters: Number of +1/+1 counters.
        minus_one_counters: Number of -1/-1 counters.
        is_token: Whether this object is a token (for SBA checks).
    """

    def __init__(
        self,
        name: str = "",
        mana_cost: ManaCost | None = None,
        card_types: set[CardType] | None = None,
        subtypes: set[str] | None = None,
        supertypes: set[Supertype] | None = None,
        keywords: Keyword | None = None,
        rules_text: str = "",
        owner: Player | None = None,
        controller: Player | None = None,
        base_power: int = 0,
        base_toughness: int = 0,
    ) -> None:
        # Always include CREATURE in card_types.
        card_types = (card_types or set()) | {CardType.CREATURE}
        super().__init__(
            name=name,
            mana_cost=mana_cost,
            card_types=card_types,
            subtypes=subtypes,
            supertypes=supertypes,
            keywords=keywords,
            rules_text=rules_text,
            owner=owner,
            controller=controller,
        )
        self.base_power: int = base_power
        self.base_toughness: int = base_toughness
        self.damage_marked: int = 0
        self.is_tapped: bool = False
        self.summoning_sick: bool = True
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.is_token: bool = False
        self.dealt_deathtouch_damage: bool = False
        # Snapshot original P/T and counter values for continuous-effect reset.
        self._original_base_power: int = base_power
        self._original_base_toughness: int = base_toughness
        self._original_plus_one_counters: int = 0
        self._original_minus_one_counters: int = 0

    def _reset_characteristics(self) -> None:
        """Reset creature characteristics to pre-effect values."""
        super()._reset_characteristics()
        self.base_power = self._original_base_power
        self.base_toughness = self._original_base_toughness
        self.plus_one_counters = self._original_plus_one_counters
        self.minus_one_counters = self._original_minus_one_counters

    @property
    def power(self) -> int:
        """Current power including counter modifications."""
        return self.base_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        """Current toughness including counter modifications."""
        return self.base_toughness + self.plus_one_counters - self.minus_one_counters


# ---------------------------------------------------------------------------
# Instant / Sorcery
# ---------------------------------------------------------------------------

class Instant(CardImpl):
    """An instant spell — no extra fields beyond CardImpl."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["card_types"] = (kwargs.get("card_types") or set()) | {CardType.INSTANT}
        super().__init__(**kwargs)


class Sorcery(CardImpl):
    """A sorcery spell — no extra fields beyond CardImpl."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["card_types"] = (kwargs.get("card_types") or set()) | {CardType.SORCERY}
        super().__init__(**kwargs)


# ---------------------------------------------------------------------------
# Enchantment
# ---------------------------------------------------------------------------

class Enchantment(CardImpl):
    """An enchantment card.

    For auras, use the :class:`Aura` subclass which sets ``is_aura = True``.
    The base ``Enchantment`` class retains the ``attached_to`` attribute for
    backwards compatibility but marks ``is_aura = False`` so that state-based
    actions do not treat a non-aura enchantment as an unattached aura.

    Attributes:
        attached_to: The object this enchantment is attached to (``None``
            if not an aura or not yet attached).
        is_aura: ``False`` for regular enchantments; ``True`` for auras.
    """

    is_aura: bool = False

    def __init__(self, attached_to: Any | None = None, **kwargs: Any) -> None:
        kwargs["card_types"] = (kwargs.get("card_types") or set()) | {CardType.ENCHANTMENT}
        super().__init__(**kwargs)
        self.attached_to: Any | None = attached_to

    def apply_continuous_effect(self, game: GameState) -> None:
        """Apply the enchantment's continuous effect to the game."""

    def on_enchant(self, game: GameState) -> None:
        """Called when this enchantment becomes attached to an object."""

    def on_detach(self, game: GameState) -> None:
        """Called when this enchantment is detached from its object."""


class Aura(Enchantment):
    """An Aura enchantment — attaches to a permanent on the battlefield.

    Sets ``is_aura = True`` so that state-based actions correctly identify
    this as an aura (and move it to the graveyard when unattached).

    Attributes:
        is_aura: Always ``True`` for auras.
    """

    is_aura: bool = True

    def __init__(self, attached_to: Any | None = None, **kwargs: Any) -> None:
        super().__init__(attached_to=attached_to, **kwargs)


# ---------------------------------------------------------------------------
# Artifact / ArtifactCreature
# ---------------------------------------------------------------------------

class Artifact(CardImpl):
    """An artifact card.

    Attributes:
        is_tapped: Whether the artifact is currently tapped.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs["card_types"] = (kwargs.get("card_types") or set()) | {CardType.ARTIFACT}
        super().__init__(**kwargs)
        self.is_tapped: bool = False


class ArtifactCreature(Creature):
    """An artifact creature — combines Artifact and Creature types.

    Inherits creature combat stats and behaviour from :class:`Creature`.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs["card_types"] = (kwargs.get("card_types") or set()) | {CardType.ARTIFACT, CardType.CREATURE}
        super().__init__(**kwargs)


# ---------------------------------------------------------------------------
# Planeswalker
# ---------------------------------------------------------------------------

class Planeswalker(CardImpl):
    """A planeswalker card.

    Attributes:
        starting_loyalty: The starting loyalty printed on the card.
        loyalty: Current loyalty counter value.
    """

    def __init__(
        self,
        starting_loyalty: int = 0,
        **kwargs: Any,
    ) -> None:
        kwargs["card_types"] = (kwargs.get("card_types") or set()) | {CardType.PLANESWALKER}
        super().__init__(**kwargs)
        self.starting_loyalty: int = starting_loyalty
        self.loyalty: int = starting_loyalty

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        """Return the planeswalker's loyalty abilities."""
        return []


# ---------------------------------------------------------------------------
# Land
# ---------------------------------------------------------------------------

class Land(CardImpl):
    """A land card.

    Lands are not cast — they are played via a special action. ``can_cast``
    always returns ``False``.

    Attributes:
        is_tapped: Whether the land is currently tapped.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs["card_types"] = (kwargs.get("card_types") or set()) | {CardType.LAND}
        super().__init__(**kwargs)
        self.is_tapped: bool = False

    def can_cast(self, game: GameState) -> bool:
        """Lands cannot be cast; they are played as a special action."""
        return False

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return the land's mana abilities."""
        return []
