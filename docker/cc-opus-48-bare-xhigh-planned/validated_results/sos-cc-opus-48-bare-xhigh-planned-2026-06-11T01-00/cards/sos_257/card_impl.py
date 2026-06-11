"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_INSTANT_SORCERY = {CardType.INSTANT, CardType.SORCERY}
_COLORS = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
    an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn." It's still a land.

    SOS collector number 257.

    Animation is performed in place (the same permanent gains the creature
    type, base 2/4, and the Wizard subtype) so it remains a land.  Creature
    P/T attributes are only present once animated; the ``power``/``toughness``
    properties deliberately raise ``AttributeError`` beforehand so the
    unanimated land is not seen as a 0/0 creature by state-based actions.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n{T}, Pay 1 life: Add one mana of any color. Spend "
            "this mana only to cast an instant or sorcery spell.\n{5}: If this "
            "land isn't a creature, it becomes a 2/4 Wizard creature with "
            '"Whenever you cast an instant or sorcery spell, this creature '
            'gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Creature characteristics (only meaningful once animated)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        if not hasattr(self, "base_power"):
            raise AttributeError("power")
        return (
            self.modified_power
            + getattr(self, "plus_one_counters", 0)
            - getattr(self, "minus_one_counters", 0)
        )

    @property
    def toughness(self) -> int:
        if not hasattr(self, "base_toughness"):
            raise AttributeError("toughness")
        return (
            self.modified_toughness
            + getattr(self, "plus_one_counters", 0)
            - getattr(self, "minus_one_counters", 0)
        )

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        if hasattr(self, "base_power"):
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness
            self.plus_one_counters = getattr(self, "_base_plus_one_counters", 0)
            self.minus_one_counters = getattr(self, "_base_minus_one_counters", 0)

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _add_colorless(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _pay_life_cost(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            ctrl = src.controller
            if ctrl is None or ctrl.life < 1:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _add_any_restricted(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            color = ctrl.choose(_COLORS, "choose a color of mana to add")
            if color not in _COLORS:
                color = _COLORS[0]
            ctrl.mana_pool.add(color, 1, instant_sorcery_only=True)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_pay_life_cost,
                mana_produced=_add_any_restricted,
                description="{T}, Pay 1 life: Add one mana of any color. "
                "Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]

    # ------------------------------------------------------------------
    # Activated ability: {5} animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pay_five(game: "GameState", src: Any) -> bool:
            ctrl = src.controller
            if ctrl is None:
                return False
            cost = ManaCost(generic=5)
            # Restricted (instant/sorcery-only) mana cannot pay an ability cost.
            if not ctrl.mana_pool.can_pay(cost, allow_restricted=False):
                return False
            return ctrl.mana_pool.pay(cost, allow_restricted=False)

        def _animate(game: "GameState") -> None:
            source._become_creature(game)

        return [
            ActivatedAbility(
                cost=_pay_five,
                effect=_animate,
                description="{5}: If this land isn't a creature, it becomes a "
                "2/4 Wizard creature (still a land).",
            )
        ]

    # ------------------------------------------------------------------
    # Animation + pump
    # ------------------------------------------------------------------

    def _become_creature(self, game: "GameState") -> None:
        """Mutate in place into a 2/4 Wizard creature (still a land)."""
        if CardType.CREATURE in self.card_types:
            return  # already a creature — do nothing
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        # Persist the creature type through continuous-effect resets.
        self._original_card_types = frozenset(self.card_types)
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self._base_plus_one_counters = 0
        self._base_minus_one_counters = 0
        self.damage_marked = 0
        self.is_attacking = False
        self.is_blocking = False
        # It has been on the battlefield, so no summoning sickness concern.
        self.summoning_sick = False
        self.is_token = False
        self.dealt_deathtouch_damage = False
        self._register_pump(game)

    def register_triggers(self, game: "GameState") -> None:
        # Re-register the pump if this permanent re-enters while already
        # animated (the unanimated land has no triggers).
        if CardType.CREATURE in self.card_types:
            self._register_pump(game)

    def _register_pump(self, game: "GameState") -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(game: Any, event: Any) -> bool:
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if caster is not source.controller:
                return False
            if CardType.CREATURE not in source.card_types:
                return False
            card = getattr(event, "card", None)
            return bool(card is not None and getattr(card, "card_types", set()) & _INSTANT_SORCERY)

        def _effect(game: "GameState") -> None:
            # +1/+0 until end of turn; stacks per spell, reset by the cleanup
            # step's continuous-effect reset (_reset_characteristics).
            if hasattr(source, "modified_power"):
                source.modified_power += 1

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=getattr(self, "controller", None) or game.active_player,
            )
        )


def _tap_cost(game: "GameState", source: Any) -> bool:
    """Tap *source* if untapped; return whether the cost was paid."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True
