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
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with "
            '"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn." '
            "It's still a land.",
        )
        super().__init__(**kwargs)
        self.is_animated: bool = False
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self._original_subtypes_snapshot: frozenset[str] = frozenset(self.subtypes)

    @property
    def power(self) -> int:
        """Return the Hall's current power."""
        return self.modified_power

    @property
    def toughness(self) -> int:
        """Return the Hall's current toughness."""
        return self.modified_toughness

    def _reset_characteristics(self) -> None:
        """Reset characteristics and reapply the Hall's permanent animation state."""
        super()._reset_characteristics()
        self.subtypes = set(self._original_subtypes_snapshot)
        self.base_power = 0
        self.base_toughness = 0
        self.modified_power = 0
        self.modified_toughness = 0

        if self.is_animated:
            self.card_types.add(CardType.CREATURE)
            self.subtypes.add("Wizard")
            self.base_power = 2
            self.base_toughness = 4
            self.modified_power = 2
            self.modified_toughness = 4

    def _ensure_spell_trigger_registered(self, game: GameState) -> None:
        """Register the printed spell-cast trigger once."""
        if game.trigger_manager.get_triggers_for_source(self):
            return

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return False
            if not source.is_animated:
                return False
            if not game.get_battlefield(current_controller).contains(source):
                return False
            if event.player is not current_controller and event.controller is not current_controller:
                return False
            spell = getattr(event, "spell", None) or getattr(event, "card", None)
            return _is_instant_or_sorcery(spell)

        def _effect(game: GameState) -> None:
            current_controller = getattr(source, "controller", None)
            if current_controller is None:
                return
            if not game.get_battlefield(current_controller).contains(source):
                return

            def _apply(game: GameState) -> None:
                if not source.is_animated:
                    return
                controller = getattr(source, "controller", None)
                if controller is None or not game.get_battlefield(controller).contains(source):
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

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return Great Hall's two mana abilities."""
        source = self

        def _tap_cost(game: GameState, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _colorless_effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _restricted_cost(game: GameState, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _restricted_effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
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
            restriction = (
                lambda context: (
                    isinstance(context, dict)
                    and context.get("usage") == "cast_spell"
                    and _is_instant_or_sorcery(context.get("card"))
                )
            )
            add_restricted = getattr(controller.mana_pool, "add_restricted", None)
            if callable(add_restricted):
                add_restricted(chosen_color, 1, restriction)
            else:
                controller.mana_pool.add(chosen_color, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_restricted_cost,
                mana_produced=_restricted_effect,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
                    "to cast an instant or sorcery spell."
                ),
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return Great Hall's animation ability."""
        source = self
        activation_cost = ManaCost.parse("{5}")

        def _cost(game: GameState, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if not controller.mana_pool.can_pay(activation_cost):
                return False
            return controller.mana_pool.pay(activation_cost)

        def _effect(game: GameState) -> None:
            if source.is_animated:
                return
            source.is_animated = True
            source._ensure_spell_trigger_registered(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature "
                    "with \"Whenever you cast an instant or sorcery spell, this creature "
                    "gets +1/+0 until end of turn.\" It's still a land."
                ),
            )
        ]
