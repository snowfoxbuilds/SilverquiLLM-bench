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


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex."""

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
        self._original_subtypes: frozenset[str] = frozenset(self.subtypes)
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self._is_animated: bool = False
        self._animation_effects_registered: bool = False

    @property
    def power(self) -> int:
        return self.modified_power

    @property
    def toughness(self) -> int:
        return self.modified_toughness

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        self.subtypes = set(self._original_subtypes)
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness

    def _is_on_battlefield(self, game: GameState) -> bool:
        return any(
            game.get_battlefield(player).contains(self)
            for player in game.players
        )

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_for_colorless(game: GameState, permanent: Any) -> bool:
            if getattr(permanent, "is_tapped", False):
                return False
            permanent.is_tapped = True
            return True

        def _add_colorless(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _tap_pay_life(game: GameState, permanent: Any) -> bool:
            controller = getattr(permanent, "controller", None)
            if controller is None or getattr(permanent, "is_tapped", False):
                return False
            if controller.life <= 0:
                return False
            permanent.is_tapped = True
            controller.life -= 1
            return True

        def _add_restricted_any_color(game: GameState) -> None:
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
                "Choose a color of mana to add",
            )

            def _can_spend(usage: str, obj: Any | None = None) -> bool:
                if usage != "cast_spell" or obj is None:
                    return False
                card_types = getattr(obj, "card_types", set())
                return (
                    CardType.INSTANT in card_types
                    or CardType.SORCERY in card_types
                )

            controller.mana_pool.add_restricted(choice, 1, can_spend=_can_spend)

        return [
            ManaAbility(
                cost=_tap_for_colorless,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_pay_life,
                mana_produced=_add_restricted_any_color,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this "
                    "mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    def _register_animation_effects(self, game: GameState) -> None:
        if self._animation_effects_registered:
            return

        source = self

        def _apply_type(game: GameState) -> None:
            if not source._is_animated or not source._is_on_battlefield(game):
                return
            source.card_types.add(CardType.CREATURE)
            source.subtypes.add("Wizard")

        def _apply_pt(game: GameState) -> None:
            if not source._is_animated or not source._is_on_battlefield(game):
                return
            source.modified_power = 2
            source.modified_toughness = 4

        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.TYPE,
                apply=_apply_type,
                duration=DURATION_PERMANENT,
            )
        )
        game.effect_manager.add(
            ContinuousEffect(
                source=self,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.SET_PT,
                apply=_apply_pt,
                duration=DURATION_PERMANENT,
            )
        )
        self._animation_effects_registered = True

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: GameState, permanent: Any) -> bool:
            controller = getattr(permanent, "controller", None)
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost.parse("{5}"))

        def _effect(game: GameState) -> None:
            if CardType.CREATURE in source.card_types or source._is_animated:
                return
            source._is_animated = True
            source._register_animation_effects(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature with a spell-cast trigger. It's still a land."
                ),
            )
        ]

    def register_triggers(self, game: GameState) -> None:
        game.trigger_manager.unregister(self)
        source = self
        controller = self.controller if self.controller is not None else game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
            if not source._is_on_battlefield(game):
                return False
            if not source._is_animated:
                return False
            if CardType.CREATURE not in source.card_types:
                return False
            if event.controller is not source.controller:
                return False
            spell = event.spell if event.spell is not None else event.card
            card_types = getattr(spell, "card_types", set())
            return (
                CardType.INSTANT in card_types
                or CardType.SORCERY in card_types
            )

        def _effect(game: GameState) -> None:
            def _apply_buff(game: GameState) -> None:
                if not source._is_on_battlefield(game):
                    return
                if not source._is_animated:
                    return
                if CardType.CREATURE not in source.card_types:
                    return
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
