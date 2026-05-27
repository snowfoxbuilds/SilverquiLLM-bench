"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, CardImpl, Land, ManaAbility
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
    """Return whether *obj* is on any player's battlefield."""
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
            '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard creature with '
            '"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn." '
            "It's still a land.",
        )
        super().__init__(**kwargs)
        self.base_power: int | None = None
        self.base_toughness: int | None = None
        self.modified_power: int | None = None
        self.modified_toughness: int | None = None
        self.damage_marked: int = 0
        self.summoning_sick: bool = False
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self._biblioplex_animated: bool = False
        self._biblioplex_animation_effects_registered: bool = False

    @property
    def power(self) -> int | None:
        """Return the current power if this land is animated."""
        if self.modified_power is not None:
            return self.modified_power
        return self.base_power

    @property
    def toughness(self) -> int | None:
        """Return the current toughness if this land is animated."""
        if self.modified_toughness is not None:
            return self.modified_toughness
        return self.base_toughness

    def _reset_characteristics(self) -> None:
        """Reset the animated creature characteristics before reapplying effects."""
        super()._reset_characteristics()
        self.base_power = None
        self.base_toughness = None
        self.modified_power = None
        self.modified_toughness = None

    def on_leave_battlefield(self, game: "GameState") -> None:
        """Clear battlefield-only animation state when Great Hall changes zones."""
        self._biblioplex_animated = False
        self._biblioplex_animation_effects_registered = False
        if hasattr(game, "effect_manager"):
            for effect in list(game.effect_manager.get_effects_by_source(self)):
                game.effect_manager.remove(effect)
        self._reset_characteristics()

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return Great Hall's two mana abilities."""
        source = self

        def _tap_cost(_game: GameState, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _colorless_effect(_game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _life_tap_cost(_game: GameState, src: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            if getattr(src, "is_tapped", False):
                return False
            if controller.life < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _restricted_color_effect(_game: GameState) -> None:
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
            restriction = CardImpl.make_spell_type_mana_restriction(
                {CardType.INSTANT, CardType.SORCERY},
                description="Spend this mana only to cast an instant or sorcery spell.",
            )
            controller.mana_pool.add(
                chosen_color,
                1,
                restriction=restriction,
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
            ),
        ]

    def _register_animation_effects(self, game: "GameState") -> None:
        """Register the permanent type and power/toughness effects once."""
        if self._biblioplex_animation_effects_registered:
            return
        source = self

        def _apply_type(game: GameState) -> None:
            if not source._biblioplex_animated or not _is_on_battlefield(game, source):
                return
            source.card_types.add(CardType.CREATURE)
            source.subtypes.add("Wizard")

        def _apply_set_pt(game: GameState) -> None:
            if not source._biblioplex_animated or not _is_on_battlefield(game, source):
                return
            if CardType.CREATURE not in source.card_types:
                return
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4

        game.effect_manager.add(
            ContinuousEffect(
                source=source,
                layer=Layer.TYPE,
                sublayer=None,
                apply=_apply_type,
                duration=DURATION_PERMANENT,
            )
        )
        game.effect_manager.add(
            ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.SET_PT,
                apply=_apply_set_pt,
                duration=DURATION_PERMANENT,
            )
        )
        self._biblioplex_animation_effects_registered = True

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return Great Hall's animation ability."""
        source = self

        def _cost(_game: GameState, _src: Any) -> bool:
            controller = source.controller
            if controller is None:
                return False
            cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(cost):
                return False
            return controller.mana_pool.pay(cost)

        def _effect(game: GameState) -> None:
            if CardType.CREATURE in source.card_types:
                return
            source._biblioplex_animated = True
            source._register_animation_effects(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
                    'creature with "Whenever you cast an instant or sorcery spell, '
                    'this creature gets +1/+0 until end of turn." It\'s still a land.'
                ),
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        """Register the spell-cast pump trigger once."""
        if any(
            trigger.event_type is SpellCastTriggeredEvent
            for trigger in game.trigger_manager.get_triggers_for_source(self)
        ):
            return

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: GameState, event: SpellCastTriggeredEvent) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.player is not ctrl:
                return False
            if not _is_on_battlefield(game, source):
                return False
            if CardType.CREATURE not in getattr(source, "card_types", set()):
                return False
            spell = event.spell or event.card
            if spell is None:
                return False
            card_types = getattr(spell, "card_types", set())
            return (
                CardType.INSTANT in card_types
                or CardType.SORCERY in card_types
            )

        def _effect(game: GameState) -> None:
            if not _is_on_battlefield(game, source):
                return
            if CardType.CREATURE not in getattr(source, "card_types", set()):
                return

            hall_ref = source

            def _apply_pump(current_game: GameState) -> None:
                if not _is_on_battlefield(current_game, hall_ref):
                    return
                if CardType.CREATURE not in getattr(hall_ref, "card_types", set()):
                    return
                if hall_ref.modified_power is None:
                    hall_ref.modified_power = hall_ref.base_power or 0
                hall_ref.modified_power += 1

            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.MODIFY_PT,
                    apply=_apply_pump,
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
