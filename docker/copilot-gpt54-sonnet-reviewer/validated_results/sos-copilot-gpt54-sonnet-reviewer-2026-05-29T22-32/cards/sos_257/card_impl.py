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
from engine.mana import ManaSpendRestriction
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, card: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False


def _tap_cost(game: Any, source: Any) -> bool:
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex."""

    _INSTANT_OR_SORCERY_RESTRICTION = ManaSpendRestriction(
        description="Spend this mana only to cast an instant or sorcery spell.",
        can_spend_on_spell=lambda spell: (
            CardType.INSTANT in getattr(spell, "card_types", set())
            or CardType.SORCERY in getattr(spell, "card_types", set())
        ),
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault("mana_cost", ManaCost())
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
            "to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            "creature with \"Whenever you cast an instant or sorcery spell, "
            "this creature gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        self.base_power = 0
        self.base_toughness = 0
        self.modified_power = 0
        self.modified_toughness = 0
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self._animated = False
        self._spell_trigger_registered = False
        self._original_subtypes = frozenset(self.subtypes)

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        self.subtypes = set(self._original_subtypes)
        self.modified_power = 0
        self.modified_toughness = 0
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        if self._animated:
            self.card_types.add(CardType.CREATURE)
            self.subtypes.add("Wizard")
            self.modified_power = 2
            self.modified_toughness = 4

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _colorless_effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _life_tap_cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if getattr(src, "is_tapped", False):
                return False
            if controller is None or getattr(controller, "life", 0) < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _restricted_color_effect(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            choice = controller.choose(
                [
                    ManaType.WHITE,
                    ManaType.BLUE,
                    ManaType.BLACK,
                    ManaType.RED,
                    ManaType.GREEN,
                ],
                "Choose a color of mana to produce",
            )
            if choice not in {
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            }:
                return
            controller.mana_pool.add(
                choice,
                1,
                restriction=self._INSTANT_OR_SORCERY_RESTRICTION,
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
                    "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
                    "only to cast an instant or sorcery spell."
                ),
                spend_restriction=self._INSTANT_OR_SORCERY_RESTRICTION,
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(cost):
                return False
            return controller.mana_pool.pay(cost)

        def _effect(game: Any) -> None:
            if source._animated:
                return
            source._animated = True
            source._ensure_spell_trigger(game)
            game.effect_manager.apply_all(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
                    "creature with a cast trigger. It's still a land."
                ),
            )
        ]

    def _ensure_spell_trigger(self, game: "GameState") -> None:
        if self._spell_trigger_registered or self.controller is None:
            return
        source = self
        controller = self.controller

        def _condition(game: Any, event: SpellCastTriggeredEvent) -> bool:
            if not source._animated or not _is_on_battlefield(game, source):
                return False
            if event.player is not controller:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            if spell is None:
                return False
            return (
                CardType.INSTANT in getattr(spell, "card_types", set())
                or CardType.SORCERY in getattr(spell, "card_types", set())
            )

        def _effect(game: Any) -> None:
            if not _is_on_battlefield(game, source):
                return

            def _apply_buff(g: Any) -> None:
                if _is_on_battlefield(g, source):
                    source.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
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
                controller=controller,
            )
        )
        self._spell_trigger_registered = True
