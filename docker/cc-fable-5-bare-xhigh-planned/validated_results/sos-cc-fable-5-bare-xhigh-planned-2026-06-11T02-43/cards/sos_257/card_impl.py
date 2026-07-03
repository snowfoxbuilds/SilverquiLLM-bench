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
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to
    cast an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature
    gets +1/+0 until end of turn." It's still a land.

    SOS collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n{T}, Pay 1 life: Add one mana of any color. "
            "Spend this mana only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        self._animated: bool = False

    # ------------------------------------------------------------------
    # Creature characteristics (meaningful only once animated; before
    # animation the attributes don't exist, so hasattr checks stay False)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        return (
            self.modified_power
            + self.plus_one_counters
            - self.minus_one_counters
        )

    @property
    def toughness(self) -> int:
        return (
            self.modified_toughness
            + self.plus_one_counters
            - self.minus_one_counters
        )

    def _reset_characteristics(self) -> None:
        """Reset for effect recalculation; clears the until-EOT pump."""
        super()._reset_characteristics()
        if self._animated:
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness
            self.plus_one_counters = self._base_plus_one_counters
            self.minus_one_counters = self._base_minus_one_counters

    def register_triggers(self, game: "GameState") -> None:
        """On entering the battlefield this is a fresh, un-animated land."""
        self._animated = False
        self.card_types = {CardType.LAND}
        self._original_card_types = frozenset(self.card_types)
        self.subtypes.discard("Wizard")

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: "GameState", src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life_cost(game: "GameState", src: Any) -> bool:
            controller = source.controller
            if controller is None or controller.life < 1:
                return False
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_restricted_any_color(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            chosen = controller.choose(list(_COLORS), "Choose a color of mana")
            if chosen not in _COLORS:
                chosen = _COLORS[0]
            controller.mana_pool.add_restricted(chosen, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life_cost,
                mana_produced=_add_restricted_any_color,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pay_five(game: "GameState", src: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _animate(game: "GameState") -> None:
            if CardType.CREATURE in source.card_types:
                return  # only if this land isn't a creature
            source._animated = True
            source.card_types.add(CardType.CREATURE)
            # The animation has no duration, so it survives the effect
            # manager's characteristic resets.
            source._original_card_types = frozenset(source.card_types)
            source.subtypes.add("Wizard")
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4
            source.damage_marked = 0
            # It has been on the battlefield, so it can attack right away.
            source.summoning_sick = False
            source.is_attacking = False
            source.is_blocking = False
            source.plus_one_counters = 0
            source.minus_one_counters = 0
            source._base_plus_one_counters = 0
            source._base_minus_one_counters = 0
            source.dealt_deathtouch_damage = False
            source._register_pump_trigger(game)

        return [
            ActivatedAbility(
                cost=_pay_five,
                effect=_animate,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature with \"Whenever you cast an instant or "
                    "sorcery spell, this creature gets +1/+0 until end of "
                    "turn.\" It's still a land."
                ),
            )
        ]

    def _register_pump_trigger(self, game: "GameState") -> None:
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(g: Any, event: Any) -> bool:
            ctrl = source.controller
            caster = getattr(event, "controller", None) or getattr(event, "player", None)
            if ctrl is None or caster is not ctrl:
                return False
            card = getattr(event, "card", None)
            return bool(getattr(card, "card_types", set()) & _INSTANT_SORCERY)

        def _effect(g: "GameState") -> None:
            # Direct +1/+0; cleared at cleanup via _reset_characteristics.
            if CardType.CREATURE in source.card_types:
                source.modified_power += 1

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )
