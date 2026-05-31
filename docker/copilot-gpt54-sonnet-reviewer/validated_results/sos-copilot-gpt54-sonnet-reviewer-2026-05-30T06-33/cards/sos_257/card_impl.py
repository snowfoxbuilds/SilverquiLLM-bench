"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.events import SpellCastTriggeredEvent
from engine.mana import restrict_to_spell_types
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_HALL_RESTRICTION_TEXT = "Spend this mana only to cast an instant or sorcery spell."


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast "
            "an instant or sorcery spell.\n"
            '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard creature with '
            '"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until '
            'end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        self._animated: bool = False
        self._base_power: int = 0
        self._base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self._base_plus_one_counters: int = 0
        self._base_minus_one_counters: int = 0

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        self.modified_power = 0
        self.modified_toughness = 0
        self.plus_one_counters = self._base_plus_one_counters
        self.minus_one_counters = self._base_minus_one_counters
        if self._animated:
            self.card_types.add(CardType.CREATURE)
            self.subtypes.add("Wizard")
            self.modified_power = 2
            self.modified_toughness = 4

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(_game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _life_tap_cost(_game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if getattr(src, "is_tapped", False) or controller is None or controller.life < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _colorless_effect(_game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _restricted_color_effect(_game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            chosen_color = controller.choose(
                [
                    ManaType.WHITE,
                    ManaType.BLUE,
                    ManaType.BLACK,
                    ManaType.RED,
                    ManaType.GREEN,
                ],
                "Choose a color of mana to produce",
            )
            controller.mana_pool.add(
                chosen_color,
                1,
                restriction_description=_HALL_RESTRICTION_TEXT,
                spend_restriction=restrict_to_spell_types(
                    CardType.INSTANT,
                    CardType.SORCERY,
                ),
            )

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_life_tap_cost,
                mana_produced=_restricted_color_effect,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. "
                    "Spend this mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(_game: Any, _src: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            activation_cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(activation_cost):
                return False
            return controller.mana_pool.pay(activation_cost)

        def _effect(_game: "GameState") -> None:
            if source._animated:
                return
            source._animated = True

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard creature with '
                    '"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 '
                    'until end of turn." It\'s still a land.'
                ),
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        existing = [
            trigger
            for trigger in game.trigger_manager.get_triggers_for_source(self)
            if trigger.event_type is SpellCastTriggeredEvent
        ]
        if existing:
            return

        def _condition(_game: "GameState", event: SpellCastTriggeredEvent) -> bool:
            controller = self.controller
            if controller is None or event.player is not controller:
                return False
            if CardType.CREATURE not in self.card_types:
                return False
            if not controller.zones[Zone.BATTLEFIELD].contains(self):
                return False
            spell_types = getattr(event.spell, "card_types", set())
            return CardType.INSTANT in spell_types or CardType.SORCERY in spell_types

        def _effect(resolving_game: "GameState") -> None:
            if self.controller is None or not self.controller.zones[Zone.BATTLEFIELD].contains(self):
                return

            def _apply_buff(_game: Any) -> None:
                controller = self.controller
                if controller is not None and controller.zones[Zone.BATTLEFIELD].contains(self):
                    self.modified_power += 1

            resolving_game.effect_manager.add(
                ContinuousEffect(
                    source=self,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply_buff,
                    duration=DURATION_END_OF_TURN,
                )
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=self.controller,
            )
        )
