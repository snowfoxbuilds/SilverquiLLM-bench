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
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType
from engine.events import SpellCastTriggeredEvent

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
        kwargs.setdefault("mana_cost", ManaCost())
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with "
            '"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn." '
            "It's still a land.",
        )
        super().__init__(**kwargs)
        self._original_subtypes: frozenset[str] = frozenset(self.subtypes)
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self._is_animated: bool = False
        self._trigger_registered: bool = False
        self._animation_type_effect_ref: ContinuousEffect | None = None
        self._animation_pt_effect_ref: ContinuousEffect | None = None

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

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            _ = game
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _tap_and_pay_life(game: Any, src: Any) -> bool:
            _ = game
            controller = getattr(src, "controller", None)
            if (
                controller is None
                or getattr(src, "is_tapped", False)
                or getattr(controller, "life", 0) < 1
            ):
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_colorless(game: Any) -> None:
            _ = game
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _add_restricted_colored(game: Any) -> None:
            _ = game
            controller = getattr(source, "controller", None)
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
                "Choose a color for Great Hall of the Biblioplex",
            )
            if choice not in {
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            }:
                choice = ManaType.WHITE
            controller.mana_pool.add_instant_or_sorcery_only(choice, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_pay_life,
                mana_produced=_add_restricted_colored,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. "
                    "Spend this mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            _ = game
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _effect(game: GameState) -> None:
            if source._is_animated or CardType.CREATURE in getattr(source, "card_types", set()):
                return
            source._is_animated = True

            def _apply_type(g: Any) -> None:
                if not _is_on_battlefield(g, source):
                    return
                source.card_types.add(CardType.CREATURE)
                source.subtypes.add("Wizard")

            def _apply_pt(g: Any) -> None:
                if not _is_on_battlefield(g, source):
                    return
                source.modified_power = 2
                source.modified_toughness = 4

            source._animation_type_effect_ref = game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.TYPE,
                    apply=_apply_type,
                    duration=DURATION_PERMANENT,
                )
            )
            source._animation_pt_effect_ref = game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.SET_PT,
                    apply=_apply_pt,
                    duration=DURATION_PERMANENT,
                )
            )

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature "
                    'with "Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn." '
                    "It's still a land."
                ),
            )
        ]

    def on_leaves_battlefield(self, game: "GameState") -> None:
        self._is_animated = False
        self._trigger_registered = False
        for effect in list(game.effect_manager.get_effects_by_source(self)):
            game.effect_manager.remove(effect)
        self._animation_type_effect_ref = None
        self._animation_pt_effect_ref = None

    def register_triggers(self, game: GameState) -> None:
        if self._trigger_registered:
            return
        self._trigger_registered = True
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: SpellCastTriggeredEvent) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            if CardType.CREATURE not in getattr(source, "card_types", set()):
                return False
            caster = event.player or event.controller
            if caster is not getattr(source, "controller", None):
                return False
            spell = event.card or event.spell
            if spell is None:
                return False
            card_types = getattr(spell, "card_types", set())
            return bool(card_types & {CardType.INSTANT, CardType.SORCERY})

        def _effect(game: GameState) -> None:
            def _apply(g: Any) -> None:
                if _is_on_battlefield(g, source) and CardType.CREATURE in getattr(source, "card_types", set()):
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
