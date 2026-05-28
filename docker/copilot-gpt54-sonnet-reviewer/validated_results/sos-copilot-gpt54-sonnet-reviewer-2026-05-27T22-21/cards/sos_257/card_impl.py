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
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _is_instant_or_sorcery(card: Any) -> bool:
    """Return whether *card* is an instant or sorcery spell."""
    card_types = getattr(card, "card_types", set())
    return CardType.INSTANT in card_types or CardType.SORCERY in card_types


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
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
        self._damage_marked = 0
        self._base_subtypes = frozenset(self.subtypes)
        self._great_hall_animated = False

    @property
    def power(self) -> int:
        """Current power, if animated."""
        if CardType.CREATURE not in self.card_types:
            raise AttributeError("Great Hall of the Biblioplex is not currently a creature")
        return self.modified_power

    @property
    def toughness(self) -> int:
        """Current toughness, if animated."""
        if CardType.CREATURE not in self.card_types:
            raise AttributeError("Great Hall of the Biblioplex is not currently a creature")
        return self.modified_toughness

    @property
    def damage_marked(self) -> int:
        """Damage marked on the Hall while it is a creature."""
        if CardType.CREATURE not in self.card_types:
            raise AttributeError("Great Hall of the Biblioplex is not currently a creature")
        return self._damage_marked

    @damage_marked.setter
    def damage_marked(self, value: int) -> None:
        self._damage_marked = value

    def _reset_characteristics(self) -> None:
        """Reset mutable characteristics before continuous effects reapply."""
        super()._reset_characteristics()
        self.subtypes = set(self._base_subtypes)
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
            if getattr(controller, "life", 0) < 1:
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
            if chosen_color not in {
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            }:
                return

            controller.mana_pool.add_restricted(
                chosen_color,
                1,
                restriction=lambda spell=None, payment_context=None: _is_instant_or_sorcery(spell),
                description="Spend this mana only to cast an instant or sorcery spell.",
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
                description="{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(cost):
                return False
            return controller.mana_pool.pay(cost)

        def _effect(game: Any) -> None:
            if source._great_hall_animated:
                return
            source._great_hall_animated = True

            def _apply(game: Any) -> None:
                if not _is_on_battlefield(game, source):
                    return
                source.card_types.add(CardType.CREATURE)
                source.subtypes.add("Wizard")
                source.modified_power = 2
                source.modified_toughness = 4

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.TYPE,
                    apply=_apply,
                )
            )
            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.SET_PT,
                    apply=_apply,
                )
            )

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description="{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with a spell-cast trigger. It's still a land.",
            )
        ]

    def register_triggers(self, game: GameState) -> None:
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
            if not source._great_hall_animated:
                return False
            if not _is_on_battlefield(game, source):
                return False
            if getattr(source, "controller", None) is None:
                return False
            if event.controller is not source.controller:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            return _is_instant_or_sorcery(spell)

        def _effect(game: GameState) -> None:
            if not source._great_hall_animated or not _is_on_battlefield(game, source):
                return

            def _apply(game: Any) -> None:
                if not source._great_hall_animated or not _is_on_battlefield(game, source):
                    return
                if CardType.CREATURE not in getattr(source, "card_types", set()):
                    return
                source.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply,
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
