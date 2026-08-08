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
        # Generic (non-P/T) counter storage — e.g. "charge", "stash", "oil".
        # +1/+1 and -1/-1 counters live in dedicated fields on Creature.
        # Mutate via engine.game.add_counter / remove_counter, never by
        # writing the read-only ``counters`` view. This dict is not reset by
        # ``_reset_characteristics`` — generic counters persist across the
        # continuous-effect recalculation, unlike layer-derived stats.
        self._generic_counters: dict[str, int] = {}

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

    @property
    def counters(self) -> dict[str, int]:
        """Return a read-only view of generic counters (type → count).

        ``Creature`` overrides this to also surface ``+1/+1`` / ``-1/-1``
        counters. Only positive counts appear. Mutate counters through
        :func:`engine.game.add_counter` / :func:`~engine.game.remove_counter`
        — writing to the returned dict has no effect on the object.
        """
        return {k: v for k, v in self._generic_counters.items() if v > 0}

    # ------------------------------------------------------------------
    # Hook methods — override in subclasses / card definitions
    # ------------------------------------------------------------------

    def can_cast(self, game: GameState) -> bool:
        """Return ``True`` if this card can currently be cast."""
        return True

    def cost_reduction(self, game: GameState, targets: list[Any] | None = None) -> int:
        """Return this card's *self* generic-mana reduction for casting it.

        Override in subclasses to implement self-reduction mechanics
        (e.g. Embercleave costs {1} less for each attacking creature).
        *targets* carries the already-chosen targets so target-conditional
        reductions ("costs {3} less if it targets a tapped creature") can be
        expressed; it is ``None`` for cards that don't care. The returned
        value is clamped so generic mana cannot go below 0 — colored costs are
        never reduced. Reductions from *other* permanents come through
        :meth:`spell_cost_reduction`, not this hook.

        Returns:
            Non-negative integer representing generic mana to subtract.
        """
        return 0

    def spell_cost_reduction(
        self, game: GameState, spell: "CardImpl", caster: Player
    ) -> int:
        """Return the generic-mana reduction this permanent grants to *spell*.

        Override on a permanent (e.g. Archmage of Runes: "instant and sorcery
        spells you cast cost {1} less") to reduce the cost of *other* spells.
        The casting pipeline sweeps every battlefield permanent's hook when
        computing a spell's cost. Return 0 when the reduction does not apply.
        """
        return 0

    def alternative_costs(self, game: GameState) -> list[ManaCost]:
        """Return alternative mana costs the caster may pay instead of the
        normal mana cost (rule 118.9), e.g. Blasphemous Edict's "you may pay
        {B} rather than pay this spell's mana cost".

        Each entry fully replaces the mana cost when chosen. Return an empty
        list (the default) when no alternative is available — the caster is
        only offered a choice when this is non-empty.
        """
        return []

    def on_cast(self, game: GameState) -> None:
        """Called when the card is cast (before it goes on the stack)."""

    def on_resolve(self, game: GameState) -> None:
        """Called when the spell resolves from the stack.

        Targets are available via ``self.chosen_targets`` — set at
        resolve-time by :func:`~engine.casting._resolve_spell` from
        :attr:`StackObject.targets`, or directly by test code.
        """

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
        base_power: The printed power value (rule 208.1). Immutable after init.
        base_toughness: The printed toughness value. Immutable after init.
        modified_power: Current power after continuous effects (Layer 7c), before counters.
            Reset to ``base_power`` each effect cycle; continuous effects write here.
        modified_toughness: Current toughness after continuous effects, before counters.
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
        self.modified_power: int = base_power
        self.modified_toughness: int = base_toughness
        self.damage_marked: int = 0
        self.is_tapped: bool = False
        self.summoning_sick: bool = True
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.is_token: bool = False
        self.dealt_deathtouch_damage: bool = False
        self._base_plus_one_counters: int = 0
        self._base_minus_one_counters: int = 0

    def _reset_characteristics(self) -> None:
        """Reset creature characteristics to pre-effect values."""
        super()._reset_characteristics()
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness
        self.plus_one_counters = self._base_plus_one_counters
        self.minus_one_counters = self._base_minus_one_counters
        # Reset combat-restriction flags set by continuous effects (e.g. Pacifism).
        # These are reapplied by active effects during apply_all().
        self._cant_attack: bool = False
        self._cant_block: bool = False
        self._cant_be_blocked: bool = False
        self._cant_activate: bool = False
        self._max_attackers_blocked: int = 1
        # Clear granted protections so they are reapplied by active effects.
        if hasattr(self, "protections"):
            self.protections = []

    @property
    def counters(self) -> dict[str, int]:
        """Return a read-only view of all counters on this creature.

        Merges the dedicated ``+1/+1`` / ``-1/-1`` fields with the generic
        counter dict. Only positive counts appear. Mutate via
        :func:`engine.game.add_counter` / :func:`~engine.game.remove_counter`.
        """
        result: dict[str, int] = {k: v for k, v in self._generic_counters.items() if v > 0}
        if self.plus_one_counters > 0:
            result["+1/+1"] = self.plus_one_counters
        if self.minus_one_counters > 0:
            result["-1/-1"] = self.minus_one_counters
        return result

    @property
    def power(self) -> int:
        """Current power including counter modifications."""
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        """Current toughness including counter modifications."""
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters


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


def _obj_on_battlefield(game: GameState, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class Equipment(Artifact):
    """An Equipment artifact (rule 301.5) — a first-class attachment type.

    Equipment attaches to a creature its controller controls via a
    sorcery-speed equip ability and buffs that creature through continuous
    effects registered on attach and removed on detach. Lifecycle cleanup is
    fully engine-driven:

    * **Equipment leaves the battlefield** — ``move_to_zone`` removes every
      continuous effect keyed to this source, so the buff vanishes.
    * **Equipped creature leaves** — the attachment state-based action
      (``_sba_aura_unattached``) detaches this Equipment, which removes the
      effects.

    Subclasses declare the buff by overriding :meth:`make_equip_effects`
    (and may add triggers via ``register_triggers``). They pass ``equip_cost``
    as a real :class:`~engine.types.ManaCost` — colored pips included, no
    generic-mana approximation.

    Attributes:
        is_equipment: Always ``True`` (consulted by the attachment SBA and the
            replacement of the historical ``getattr(..., "is_equipment")``
            duck-type).
        attached_to: The creature this Equipment is attached to, or ``None``.
        equip_cost: The mana cost of the equip activated ability.
    """

    is_equipment: bool = True

    def __init__(self, *, equip_cost: ManaCost | None = None, **kwargs: Any) -> None:
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self.equip_cost: ManaCost = equip_cost if equip_cost is not None else ManaCost()
        self._equip_effect_refs: list[Any] = []

    # ------------------------------------------------------------------
    # Attach / detach lifecycle
    # ------------------------------------------------------------------

    def make_equip_effects(self, game: GameState) -> list[Any]:
        """Return the continuous effects that buff ``self.attached_to``.

        Called at attach time with ``attached_to`` already set. Override in
        subclasses. Each returned effect must use ``source=self`` and should
        self-guard via :meth:`is_equip_active` so it no-ops in the window
        between the equipped creature dying and the SBA detaching.
        """
        return []

    def is_equip_active(self, game: GameState) -> bool:
        """``True`` if both this Equipment and its equipped creature are on the
        battlefield — the condition under which the buff applies."""
        creature = self.attached_to
        if creature is None:
            return False
        return _obj_on_battlefield(game, self) and _obj_on_battlefield(game, creature)

    def equip(self, target: Any, game: GameState) -> None:
        """Attach to *target* (detaching from any previous creature first) and
        register the buff effects. Re-derives continuous effects so the buff
        takes hold immediately."""
        if target is None or self.attached_to is target:
            return
        # An Equipment attaches to only one creature at a time.
        self._remove_equip_effects(game)
        self.attached_to = target
        self.on_attach(game)
        self._register_equip_effects(game)
        self._rederive(game)

    def detach(self, game: GameState) -> None:
        """Detach from the equipped creature and remove the buff effects."""
        had_target = self.attached_to is not None
        self._remove_equip_effects(game)
        self.attached_to = None
        if had_target:
            self.on_detach(game)
            self._rederive(game)

    def on_attach(self, game: GameState) -> None:
        """Hook after this Equipment attaches (before its effects register)."""

    def on_detach(self, game: GameState) -> None:
        """Hook after this Equipment detaches."""

    def _register_equip_effects(self, game: GameState) -> None:
        mgr = getattr(game, "effect_manager", None)
        if mgr is None:
            return
        for eff in self.make_equip_effects(game):
            self._equip_effect_refs.append(mgr.add(eff))

    def _remove_equip_effects(self, game: GameState) -> None:
        mgr = getattr(game, "effect_manager", None)
        if mgr is not None:
            for eff in self._equip_effect_refs:
                mgr.remove(eff)
        self._equip_effect_refs = []

    def _rederive(self, game: GameState) -> None:
        # Always re-derive: detach may have just removed the last effect, and a
        # skipped reset would leave the departed buff baked into modified stats.
        # equip/detach are infrequent, so the full pass is cheap here.
        mgr = getattr(game, "effect_manager", None)
        if mgr is not None:
            mgr.apply_all(game)

    # ------------------------------------------------------------------
    # Equip activated ability (sorcery speed, target creature you control)
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        return [self._make_equip_ability()]

    def _make_equip_ability(self) -> ActivatedAbility:
        equipment = self

        def _cost(game: GameState, source: Any) -> bool:
            from engine.casting import is_sorcery_speed

            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            # Equip is sorcery speed (rule 702.6e).
            if not is_sorcery_speed(game, controller):
                return False
            if not controller.mana_pool.can_pay(equipment.equip_cost):
                return False
            controller.mana_pool.pay(equipment.equip_cost)
            return True

        def _effect(game: GameState) -> None:
            from engine.card_queries import choose_object

            controller = getattr(equipment, "controller", None)
            if controller is None:
                return
            # Equip can only target a creature its controller controls.
            creatures = [
                obj
                for obj in game.get_battlefield(controller).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            ]
            if not creatures:
                return
            target = choose_object(
                game,
                controller,
                creatures,
                "Choose a creature to equip",
                source_card=equipment,
            )
            if target is not None:
                equipment.equip(target, game)

        return ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description=f"Equip {equipment.equip_cost}",
        )


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
