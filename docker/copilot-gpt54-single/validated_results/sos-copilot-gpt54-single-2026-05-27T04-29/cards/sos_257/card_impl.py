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
from engine.types import CardType, ManaCost, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault("mana_cost", ManaCost())
        kwargs.setdefault("colors", set())
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with "
            "\"Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn.\" "
            "It's still a land.",
        )
        super().__init__(**kwargs)
        self.base_power = 0
        self.base_toughness = 0
        self.modified_power = 0
        self.modified_toughness = 0
        self.damage_marked = 0
        self.summoning_sick = True
        self.is_attacking = False
        self.is_blocking = False
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.is_token = False
        self.dealt_deathtouch_damage = False
        self._base_plus_one_counters = 0
        self._base_minus_one_counters = 0
        self._animated = False
        self._animation_effects: list[ContinuousEffect] = []

    def _reset_characteristics(self) -> None:
        """Reset mutable characteristics while preserving printed/base stats."""
        super()._reset_characteristics()
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness
        self.plus_one_counters = self._base_plus_one_counters
        self.minus_one_counters = self._base_minus_one_counters

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return the land's two mana abilities."""
        source = self

        def _tap_cost(_game: GameState, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _colored_cost(_game: GameState, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if getattr(src, "is_tapped", False):
                return False
            if controller.life <= 0:
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _add_colorless(_game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _instant_or_sorcery_only(card: object | None) -> bool:
            card_types = getattr(card, "card_types", set())
            return (
                CardType.INSTANT in card_types
                or CardType.SORCERY in card_types
            )

        def _add_restricted_color(_game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            chosen = controller.choose(
                [
                    ManaType.WHITE,
                    ManaType.BLUE,
                    ManaType.BLACK,
                    ManaType.RED,
                    ManaType.GREEN,
                ],
                "Choose a color for Great Hall of the Biblioplex",
            )
            if chosen not in {
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            }:
                chosen = ManaType.WHITE
            controller.mana_pool.add(
                chosen,
                1,
                restriction=_instant_or_sorcery_only,
                description="Spend this mana only to cast an instant or sorcery spell.",
            )

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_colored_cost,
                mana_produced=_add_restricted_color,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. "
                    "Spend this mana only to cast an instant or sorcery spell."
                ),
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return the animation ability."""
        source = self

        def _cost(_game: GameState, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            mana_cost = ManaCost(generic=5)
            if not controller.mana_pool.can_pay(mana_cost):
                return False
            return controller.mana_pool.pay(mana_cost)

        def _effect(game: GameState) -> None:
            if CardType.CREATURE in source.card_types or source._animated:
                return
            source._animated = True
            source._animation_effects = source._create_animation_effects(game)
            source.register_triggers(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature "
                    "with a spell-cast power trigger. It's still a land."
                ),
            )
        ]

    @staticmethod
    def _is_on_battlefield(game: GameState, permanent: Any) -> bool:
        for player in game.players:
            if game.get_battlefield(player).contains(permanent):
                return True
        return False

    def _create_animation_effects(self, game: GameState) -> list[ContinuousEffect]:
        source = self

        def _apply_type_change(g: GameState) -> None:
            if not source._animated or not source._is_on_battlefield(g, source):
                return
            source.card_types = set(source.card_types) | {CardType.CREATURE}
            source.subtypes = set(source.subtypes) | {"Wizard"}

        def _apply_pt(g: GameState) -> None:
            if not source._animated or not source._is_on_battlefield(g, source):
                return
            source.modified_power = 2
            source.modified_toughness = 4

        return [
            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.TYPE,
                    apply=_apply_type_change,
                    duration=DURATION_PERMANENT,
                )
            ),
            game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.SET_PT,
                    apply=_apply_pt,
                    duration=DURATION_PERMANENT,
                )
            ),
        ]

    def _clear_animation_state(self, game: GameState) -> None:
        for effect in list(self._animation_effects):
            game.effect_manager.remove(effect)
        self._animation_effects = []
        self._animated = False
        self._reset_characteristics()

    def register_triggers(self, game: GameState) -> None:
        """Register the animated spell-cast trigger, if present."""
        if not self._animated or not self._is_on_battlefield(game, self):
            return
        if any(trigger.source is self for trigger in game.trigger_manager.get_triggers_for_source(self)):
            return

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(_game: GameState, event: SpellCastTriggeredEvent) -> bool:
            spell = event.spell or event.card
            if spell is None:
                return False
            caster = event.player or event.controller or getattr(spell, "controller", None)
            if caster is not getattr(source, "controller", None):
                return False
            card_types = getattr(spell, "card_types", set())
            return (
                CardType.INSTANT in card_types
                or CardType.SORCERY in card_types
            )

        def _effect(game: GameState) -> None:
            def _apply(_game: GameState, hall: GreatHallOfTheBiblioplex = source) -> None:
                if not hall._is_on_battlefield(_game, hall):
                    return
                hall.modified_power += 1

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

    def on_zone_change(self, game: GameState, from_zone: Zone, to_zone: Zone) -> None:
        """Clear the animation if the Hall leaves the battlefield."""
        if from_zone == Zone.BATTLEFIELD and to_zone != Zone.BATTLEFIELD:
            self._clear_animation_state(game)
