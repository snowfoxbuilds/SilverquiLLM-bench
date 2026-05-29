"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, CreatureStateMixin, Land, ManaAbility
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.events import SpellCastTriggeredEvent
from engine.mana import ManaRestriction
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Return whether *obj* is currently on a battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class GreatHallOfTheBiblioplex(CreatureStateMixin, Land):
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
        self._init_creature_state(base_power=0, base_toughness=0)
        self._biblioplex_animated: bool = False
        self._animation_type_effect_ref: ContinuousEffect | None = None
        self._animation_pt_effect_ref: ContinuousEffect | None = None
        self._instant_sorcery_mana_restriction = ManaRestriction(
            description="Spend this mana only to cast an instant or sorcery spell.",
            allowed_actions=frozenset({"cast_spell"}),
            allowed_card_types=frozenset({CardType.INSTANT, CardType.SORCERY}),
        )

    def _reset_characteristics(self) -> None:
        """Reset mutable characteristics before continuous effects reapply."""
        super()._reset_characteristics()
        self.subtypes = set(self._original_subtypes)
        self.base_power = 0
        self.base_toughness = 0
        self._reset_creature_state()

    def register_triggers(self, game: "GameState") -> None:
        """Register the static spell-cast trigger and animation effects."""
        self._biblioplex_animated = False
        self._ensure_animation_effects(game)

        source = self
        controller = self.controller or game.active_player

        def _condition(game: Any, event: SpellCastTriggeredEvent) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            if not getattr(source, "_biblioplex_animated", False):
                return False
            if getattr(event, "controller", None) is not getattr(source, "controller", None):
                return False
            spell = getattr(event, "card", None) or getattr(event, "spell", None)
            spell_types = getattr(spell, "card_types", set())
            return (
                CardType.INSTANT in spell_types
                or CardType.SORCERY in spell_types
            )

        def _effect(game: "GameState") -> None:
            if not _is_on_battlefield(game, source):
                return
            if not getattr(source, "_biblioplex_animated", False):
                return

            def _apply_buff(g: Any) -> None:
                if not _is_on_battlefield(g, source):
                    return
                if not getattr(source, "_biblioplex_animated", False):
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
            game.recompute_effects()

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

    def _ensure_animation_effects(self, game: "GameState") -> None:
        """Register the permanent animation effects once."""
        if self._animation_type_effect_ref is None:
            source = self

            def _apply_type(g: Any) -> None:
                if not _is_on_battlefield(g, source):
                    return
                if not getattr(source, "_biblioplex_animated", False):
                    return
                source.card_types = set(source.card_types) | {CardType.CREATURE}
                source.subtypes = set(source.subtypes) | {"Wizard"}

            self._animation_type_effect_ref = game.effect_manager.add(
                ContinuousEffect(
                    source=self,
                    layer=Layer.TYPE,
                    apply=_apply_type,
                    duration=DURATION_PERMANENT,
                )
            )

        if self._animation_pt_effect_ref is None:
            source = self

            def _apply_pt(g: Any) -> None:
                if not _is_on_battlefield(g, source):
                    return
                if not getattr(source, "_biblioplex_animated", False):
                    return
                source.base_power = 2
                source.base_toughness = 4
                source.modified_power = 2
                source.modified_toughness = 4

            self._animation_pt_effect_ref = game.effect_manager.add(
                ContinuousEffect(
                    source=self,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.SET_PT,
                    apply=_apply_pt,
                    duration=DURATION_PERMANENT,
                )
            )

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return the land's mana abilities."""
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            del game
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _life_tap_cost(game: Any, src: Any) -> bool:
            del game
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if getattr(src, "is_tapped", False):
                return False
            if controller.life < 1:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _colorless_effect(game: Any) -> None:
            del game
            controller = source.controller
            if controller is None:
                return
            controller.mana_pool.add(ManaType.COLORLESS, 1, source=source)

        def _any_color_effect(game: Any) -> None:
            del game
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
                source=source,
                restriction=self._instant_sorcery_mana_restriction,
            )

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_life_tap_cost,
                mana_produced=_any_color_effect,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
                    "only to cast an instant or sorcery spell."
                ),
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the land's animation ability."""
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(cost):
                return False
            return controller.mana_pool.pay(cost)

        def _effect(game: "GameState") -> None:
            if CardType.CREATURE in source.card_types:
                return
            source._biblioplex_animated = True
            source._ensure_animation_effects(game)
            game.recompute_effects()

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature with the printed spell-cast trigger. "
                    "It's still a land."
                ),
            )
        ]
