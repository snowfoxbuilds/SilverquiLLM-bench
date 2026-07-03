"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import (
    DURATION_END_OF_TURN,
    ContinuousEffect,
    Layer,
    SubLayer,
)
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land

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
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
            "only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Pre-initialize creature P/T attributes so effect_manager resets
        # don't AttributeError when this land is animated.
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.damage_marked: int = 0
        self._pump_trigger_registered: bool = False

    def _reset_characteristics(self) -> None:
        """Reset includes P/T for when this land is animated."""
        super()._reset_characteristics()
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _tap_and_pay_life_cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _colorless_effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _any_color_effect(game: Any) -> None:
            # ENGINE LIMITATION: restricted mana spending not enforced.
            # This mana should only be used to cast instant or sorcery spells.
            controller = source.controller
            if controller is None:
                return
            color_options = [
                ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
                ManaType.RED, ManaType.GREEN,
            ]
            chosen_color = controller.choose(
                color_options,
                "Choose a color of mana to produce",
            )
            controller.mana_pool.add(chosen_color, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_pay_life_cost,
                mana_produced=_any_color_effect,
                description="{T}, Pay 1 life: Add one mana of any color (restricted to instant/sorcery).",
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _animate_cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 5:
                return False
            return controller.mana_pool.pay(ManaCost.parse("{5}"))

        def _animate_effect(game: Any) -> None:
            if CardType.CREATURE in source.card_types:
                return  # Already animated

            source.card_types |= {CardType.CREATURE}
            # Update the reset baseline so continuous-effect resets preserve CREATURE.
            source._original_card_types = frozenset(source.card_types)
            source.subtypes |= {"Wizard"}
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4

            if not source._pump_trigger_registered:
                source._pump_trigger_registered = True
                _register_pump_trigger(game)

        def _register_pump_trigger(game: Any) -> None:
            from engine.events import SpellCastTriggeredEvent
            from engine.triggers import TriggerRegistration

            def _condition(g: Any, event: Any) -> bool:
                if event.controller is not source.controller:
                    return False
                card = event.card
                if card is None:
                    return False
                card_types = getattr(card, "card_types", set())
                return (
                    CardType.INSTANT in card_types
                    or CardType.SORCERY in card_types
                )

            def _pump_effect(g: Any) -> None:
                ctrl = source.controller
                if ctrl is None:
                    return
                if not g.get_battlefield(ctrl).contains(source):
                    return
                if CardType.CREATURE not in source.card_types:
                    return

                def _apply_pump(game: Any, _s: Any = source) -> None:
                    for player in game.players:
                        if game.get_battlefield(player).contains(_s):
                            if CardType.CREATURE in _s.card_types:
                                _s.modified_power += 1
                            return

                g.effect_manager.add(ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply_pump,
                    duration=DURATION_END_OF_TURN,
                ))

            game.trigger_manager.register(
                TriggerRegistration(
                    event_type=SpellCastTriggeredEvent,
                    condition=_condition,
                    effect=_pump_effect,
                    source=source,
                    controller=source.controller,
                )
            )

        return [ActivatedAbility(
            cost=_animate_cost,
            effect=_animate_effect,
            description=(
                "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
                'creature with "Whenever you cast an instant or sorcery spell, '
                'this creature gets +1/+0 until end of turn." It\'s still a land.'
            ),
        )]
