"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
            "to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature "
            'with "Whenever you cast an instant or sorcery spell, this creature '
            "gets +1/+0 until end of turn.\" It's still a land.",
        )
        super().__init__(**kwargs)
        self._original_subtypes = frozenset(self.subtypes)
        self.base_power = 0
        self.base_toughness = 0
        self.modified_power = 0
        self.modified_toughness = 0
        self.damage_marked = 0
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.dealt_deathtouch_damage = False
        self._spell_trigger_registered = False
        self._registered_effects: list[ContinuousEffect] = []

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        self.subtypes = set(self._original_subtypes)
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness

    def on_leave_battlefield(self, game: "GameState") -> None:
        self._spell_trigger_registered = False
        for effect in list(self._registered_effects):
            game.effect_manager.remove(effect)
        self._registered_effects.clear()

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    @staticmethod
    def _restricted_spell_mana_context(spending_context: object | None) -> bool:
        card_types = getattr(spending_context, "card_types", set())
        return (
            CardType.INSTANT in card_types
            or CardType.SORCERY in card_types
        )

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _tap_and_pay_life_cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None or getattr(src, "is_tapped", False):
                return False
            if controller.life <= 0:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_colorless(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _add_restricted_colored(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            color = controller.choose(
                [
                    ManaType.WHITE,
                    ManaType.BLUE,
                    ManaType.BLACK,
                    ManaType.RED,
                    ManaType.GREEN,
                ],
                "Choose a color of mana to add",
            )
            if color not in {
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            }:
                return
            controller.mana_pool.add(
                color,
                1,
                restriction=self._restricted_spell_mana_context,
            )

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_pay_life_cost,
                mana_produced=_add_restricted_colored,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
                    "only to cast an instant or sorcery spell."
                ),
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self
        cost = ManaCost(generic=5)

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if not controller.mana_pool.can_pay(cost):
                return False
            return controller.mana_pool.pay(cost)

        def _effect(game: Any) -> None:
            if CardType.CREATURE in getattr(source, "card_types", set()):
                return

            def _apply_type(game: Any) -> None:
                if not _is_on_battlefield(game, source):
                    return
                source.card_types.add(CardType.CREATURE)
                source.subtypes.add("Wizard")

            def _apply_pt(game: Any) -> None:
                if not _is_on_battlefield(game, source):
                    return
                source.modified_power = 2
                source.modified_toughness = 4

            source._registered_effects.append(
                game.effect_manager.add(
                    ContinuousEffect(
                        source=source,
                        layer=Layer.TYPE,
                        apply=_apply_type,
                        duration=DURATION_PERMANENT,
                    ),
                )
            )
            source._registered_effects.append(
                game.effect_manager.add(
                    ContinuousEffect(
                        source=source,
                        layer=Layer.POWER_TOUGHNESS,
                        sublayer=SubLayer.SET_PT,
                        apply=_apply_pt,
                        duration=DURATION_PERMANENT,
                    ),
                )
            )

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
                    "creature. It's still a land."
                ),
            ),
        ]

    def register_triggers(self, game: "GameState") -> None:
        if self._spell_trigger_registered:
            return
        self._spell_trigger_registered = True
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: SpellCastTriggeredEvent) -> bool:
            caster = event.player or event.controller
            spell = event.spell or event.card
            if caster is not getattr(source, "controller", None):
                return False
            if spell is None:
                return False
            if not _is_on_battlefield(game, source):
                return False
            if CardType.CREATURE not in getattr(source, "card_types", set()):
                return False
            card_types = getattr(spell, "card_types", set())
            return (
                CardType.INSTANT in card_types
                or CardType.SORCERY in card_types
            )

        def _effect(game: "GameState") -> None:
            if not _is_on_battlefield(game, source):
                return

            def _apply(game: Any) -> None:
                if not _is_on_battlefield(game, source):
                    return
                if CardType.CREATURE not in getattr(source, "card_types", set()):
                    return
                source.modified_power += 1

            source._registered_effects.append(
                game.effect_manager.add(
                    ContinuousEffect(
                        source=source,
                        layer=Layer.POWER_TOUGHNESS,
                        sublayer=SubLayer.MODIFY_PT,
                        apply=_apply,
                        duration=DURATION_END_OF_TURN,
                    ),
                )
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            ),
        )
