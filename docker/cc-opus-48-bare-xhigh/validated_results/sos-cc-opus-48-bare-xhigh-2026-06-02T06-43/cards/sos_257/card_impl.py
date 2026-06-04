"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_COLORS = [
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
]


def _is_instant_or_sorcery(card: Any) -> bool:
    types = getattr(card, "card_types", set())
    return CardType.INSTANT in types or CardType.SORCERY in types


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
    an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn." It's still a land.

    SOS collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
            "to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Creature characteristics — inert until the {5} ability animates it.
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.damage_marked: int = 0
        self._pump: int = 0

    # ------------------------------------------------------------------
    # Power / toughness (live once animated)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        return (
            self.modified_power
            + self.plus_one_counters
            - self.minus_one_counters
            + self._pump
        )

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    @property
    def is_creature(self) -> bool:
        return CardType.CREATURE in self.card_types

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _tap_pay_life_cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if getattr(src, "is_tapped", False):
                return False
            if getattr(controller, "life", 0) < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _colorless(game: Any) -> None:
            if source.controller is not None:
                source.controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _any_color(game: Any) -> None:
            # ENGINE LIMITATION: the "spend only on instant/sorcery" restriction
            # is not enforced by the mana pool.
            controller = source.controller
            if controller is None:
                return
            try:
                chosen = controller.choose(_COLORS, "Choose a color of mana")
            except Exception:
                chosen = ManaType.WHITE
            if chosen not in _COLORS:
                chosen = ManaType.WHITE
            controller.mana_pool.add(chosen, 1)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_colorless, description="{T}: Add {C}."),
            ManaAbility(
                cost=_tap_pay_life_cost,
                mana_produced=_any_color,
                description="{T}, Pay 1 life: Add one mana of any color (instant/sorcery only).",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animate into a 2/4 Wizard creature
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if CardType.CREATURE in src.card_types:
                return False  # already a creature
            if controller.mana_pool.total() < 5:
                return False
            controller.mana_pool.pay(ManaCost(generic=5))
            return True

        def _effect(game: "GameState") -> None:
            source.animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{5}: Becomes a 2/4 Wizard creature; it's still a land.",
            )
        ]

    def animate(self, game: "GameState") -> None:
        """Make this land a 2/4 Wizard creature (it stays a land)."""
        if CardType.CREATURE in self.card_types:
            return
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        self.subtypes = set(self.subtypes) | {"Wizard"}
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.damage_marked = 0
        self.is_attacking = False
        self.is_blocking = False
        self.summoning_sick = False
        self._register_creature_triggers(game)

    def _register_creature_triggers(self, game: "GameState") -> None:
        from engine.events import EndStepTriggeredEvent, SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _cast_condition(game: Any, event: Any) -> bool:
            if getattr(event, "controller", None) is not source.controller:
                return False
            return _is_instant_or_sorcery(getattr(event, "card", None))

        def _cast_effect(game: "GameState") -> None:
            source._pump += 1

        def _eot_condition(game: Any, event: Any) -> bool:
            return True

        def _eot_effect(game: "GameState") -> None:
            source._pump = 0

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_cast_condition,
                effect=_cast_effect,
                source=self,
                controller=self.controller,
            )
        )
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EndStepTriggeredEvent,
                condition=_eot_condition,
                effect=_eot_effect,
                source=self,
                controller=self.controller,
            )
        )
