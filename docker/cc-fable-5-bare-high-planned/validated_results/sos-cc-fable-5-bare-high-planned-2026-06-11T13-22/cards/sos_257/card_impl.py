"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


_COLORS: list[ManaType] = [
    ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
    ManaType.RED, ManaType.GREEN,
]


def _tap_cost(game: "GameState", source: Any) -> bool:
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to
    cast an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature
    with "Whenever you cast an instant or sorcery spell, this creature
    gets +1/+0 until end of turn." It's still a land.

    SOS collector number 257.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n{T}, Pay 1 life: Add one mana of any color. "
            "Spend this mana only to cast an instant or sorcery spell.\n"
            '{5}: If this land isn\'t a creature, it becomes a 2/4 Wizard '
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Creature stats live here from the start so the power/toughness
        # properties always work; they only matter once animated.
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.damage_marked: int = 0
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.dealt_deathtouch_damage: bool = False
        self.summoning_sick: bool = False

    # ------------------------------------------------------------------
    # Creature-style P/T (used once animated)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        super()._reset_characteristics()
        self.modified_power = self.base_power
        self.modified_toughness = self.base_toughness

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _add_colorless(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def _life_tap_cost(game: "GameState", src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if not _tap_cost(game, src):
                return False
            controller.life -= 1
            return True

        def _add_restricted_color(game: "GameState") -> None:
            controller = source.controller
            if controller is None:
                return
            color = controller.choose(
                list(_COLORS), "Choose a color of mana to add (instant/sorcery only)"
            )
            if color not in _COLORS:
                color = _COLORS[0]
            controller.mana_pool.add_restricted(color, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_life_tap_cost,
                mana_produced=_add_restricted_color,
                description="{T}, Pay 1 life: Add one mana of any color. "
                "Spend this mana only to cast an instant or sorcery spell.",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animation
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pay_five(game: "GameState", src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            return controller.mana_pool.pay(ManaCost(generic=5))

        def _animate(game: "GameState") -> None:
            if CardType.CREATURE in source.card_types:
                return  # already a creature — the ability does nothing
            source.card_types.add(CardType.CREATURE)
            source.subtypes.add("Wizard")
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4
            # The animation has no duration, so make it survive continuous-
            # effect recalculation (which resets to "original" characteristics).
            source._original_card_types = frozenset(source.card_types)
            source._register_pump_trigger(game)

        return [
            ActivatedAbility(
                cost=_pay_five,
                effect=_animate,
                description="{5}: If this land isn't a creature, it becomes "
                "a 2/4 Wizard creature. It's still a land.",
            ),
        ]

    def _register_pump_trigger(self, game: "GameState") -> None:
        """'Whenever you cast an instant or sorcery spell, this creature
        gets +1/+0 until end of turn.' Registered at animation time."""
        from engine.continuous_effects import (
            DURATION_END_OF_TURN,
            ContinuousEffect,
            Layer,
            SubLayer,
        )
        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            if event.controller is not source.controller:
                return False
            if CardType.CREATURE not in source.card_types:
                return False
            return bool(getattr(event.card, "card_types", set()) & {
                CardType.INSTANT, CardType.SORCERY
            })

        def _effect(game: "GameState") -> None:
            def _apply(g: Any) -> None:
                source.modified_power += 1

            game.effect_manager.add(ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_END_OF_TURN,
            ))
            game.effect_manager.apply_all(game)

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
