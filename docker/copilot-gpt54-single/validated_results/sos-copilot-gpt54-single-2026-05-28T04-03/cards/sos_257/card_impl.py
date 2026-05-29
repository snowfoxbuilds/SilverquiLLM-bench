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
from engine.mana import ManaRestriction
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — animated spell-matters land."""

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
        self._original_subtypes: frozenset[str] = frozenset(self.subtypes)
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.damage_marked: int = 0
        self.summoning_sick: bool = True
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.is_token: bool = False
        self.dealt_deathtouch_damage: bool = False
        self._base_plus_one_counters: int = 0
        self._base_minus_one_counters: int = 0
        self._is_animated: bool = False
        self._animation_generation: int = 0
        self._animation_effects: list[ContinuousEffect] = []

    def _reset_characteristics(self) -> None:
        """Reset mutable characteristics before continuous effects reapply."""
        super()._reset_characteristics()
        self.subtypes = set(self._original_subtypes)
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness
        self.plus_one_counters = self._base_plus_one_counters
        self.minus_one_counters = self._base_minus_one_counters
        self._cant_attack = False
        self._cant_block = False
        self._cant_be_blocked = False
        self._cant_activate = False
        self._max_attackers_blocked = 1
        if hasattr(self, "protections"):
            self.protections = []

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    @property
    def counters(self) -> dict[str, int]:
        result: dict[str, int] = {}
        if self.plus_one_counters > 0:
            result["+1/+1"] = self.plus_one_counters
        if self.minus_one_counters > 0:
            result["-1/-1"] = self.minus_one_counters
        return result

    def on_leaves_battlefield(self, game: "GameState", destination: Any) -> None:
        """Clear animation state so zone changes return as a fresh land."""
        self._animation_generation += 1
        self._is_animated = False
        for effect in list(self._animation_effects):
            game.effect_manager.remove(effect)
        self._animation_effects.clear()
        self.is_tapped = False
        self.damage_marked = 0
        self.summoning_sick = True
        self.is_attacking = False
        self.is_blocking = False
        self.plus_one_counters = 0
        self.minus_one_counters = 0
        self.dealt_deathtouch_damage = False

    def _instant_or_sorcery_restriction(self) -> ManaRestriction:
        """Return the reusable spend restriction for the colored mana ability."""

        def _predicate(spend_context: Any) -> bool:
            if getattr(spend_context, "purpose", None) != "cast_spell":
                return False
            spell = getattr(spend_context, "spell", None)
            if spell is None:
                return False
            card_types = getattr(spell, "card_types", set())
            return bool(card_types & {CardType.INSTANT, CardType.SORCERY})

        return ManaRestriction(
            predicate=_predicate,
            description="Spend this mana only to cast an instant or sorcery spell.",
            source=self,
        )

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _tap_and_pay_life(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None or controller.life < 1:
                return False
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            controller.life -= 1
            return True

        def _colorless_effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _any_color_effect(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return
            colors = [
                ManaType.WHITE,
                ManaType.BLUE,
                ManaType.BLACK,
                ManaType.RED,
                ManaType.GREEN,
            ]
            chosen_color = controller.choose(
                colors,
                "Choose a color of mana to add with Great Hall of the Biblioplex",
            )
            if chosen_color not in colors:
                chosen_color = ManaType.WHITE
            controller.mana_pool.add(
                chosen_color,
                1,
                restriction=self._instant_or_sorcery_restriction(),
            )

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_tap_and_pay_life,
                mana_produced=_any_color_effect,
                description=(
                    "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
                    "only to cast an instant or sorcery spell."
                ),
            ),
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self
        activation_cost = ManaCost.parse("{5}")

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            if not controller.mana_pool.can_pay_for_ability(
                activation_cost,
                src,
                player=controller,
            ):
                return False
            return controller.mana_pool.pay_for_ability(
                activation_cost,
                src,
                player=controller,
            )

        def _effect(game: "GameState") -> None:
            if source._is_animated:
                return
            source._is_animated = True
            animation_generation = source._animation_generation

            def _apply_type(_game: Any) -> None:
                if source._animation_generation != animation_generation:
                    return
                source.card_types.add(CardType.CREATURE)
                source.subtypes.add("Wizard")

            def _apply_pt(_game: Any) -> None:
                if source._animation_generation != animation_generation:
                    return
                source.modified_power = 2
                source.modified_toughness = 4

            type_effect = game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.TYPE,
                    apply=_apply_type,
                    duration=DURATION_PERMANENT,
                )
            )
            pt_effect = game.effect_manager.add(
                ContinuousEffect(
                    source=source,
                    layer=Layer.POWER_TOUGHNESS,
                    sublayer=SubLayer.SET_PT,
                    apply=_apply_pt,
                    duration=DURATION_PERMANENT,
                )
            )
            source._animation_effects = [type_effect, pt_effect]

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
                    "creature. It's still a land."
                ),
            )
        ]

    def register_triggers(self, game: "GameState") -> None:
        """Register the granted spell-cast trigger once for this permanent."""
        if game.trigger_manager.get_triggers_for_source(self):
            return

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: SpellCastTriggeredEvent) -> bool:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return False
            if getattr(event, "player", None) is not ctrl and getattr(event, "controller", None) is not ctrl:
                return False
            if CardType.CREATURE not in getattr(source, "card_types", set()):
                return False
            spell = getattr(event, "card", None) or getattr(event, "spell", None)
            if spell is None:
                return False
            spell_types = getattr(spell, "card_types", set())
            return bool(spell_types & {CardType.INSTANT, CardType.SORCERY})

        def _effect(game: "GameState") -> None:
            animation_generation = source._animation_generation

            def _apply(_game: Any) -> None:
                if source._animation_generation != animation_generation:
                    return
                if CardType.CREATURE in getattr(source, "card_types", set()):
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

        def _stack_object_factory(
            game: "GameState",
            event: SpellCastTriggeredEvent,
            trigger: TriggerRegistration,
        ) -> StackObject:
            animation_generation = source._animation_generation

            def _resolve(game: "GameState") -> None:
                if source._animation_generation != animation_generation:
                    return
                _effect(game)

            stack_obj = StackObject(
                source=source,
                controller=trigger.controller,
                on_resolve=_resolve,
            )
            stack_obj.is_spell = False  # type: ignore[attr-defined]
            return stack_obj

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                stack_object_factory=_stack_object_factory,
            )
        )
