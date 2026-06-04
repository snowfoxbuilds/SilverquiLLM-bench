"""Card implementation for Great Hall of the Biblioplex (SOS #257)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaType, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


_ANY_COLOR_MANA = (
    ManaType.WHITE,
    ManaType.BLUE,
    ManaType.BLACK,
    ManaType.RED,
    ManaType.GREEN,
)


def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — Land — SOS #257.

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color. Spend this mana only to cast
    an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn." It's still a land.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
            "to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            'creature with "Whenever you cast an instant or sorcery spell, this '
            'creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Dormant creature machinery — only meaningful once animated.
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self._base_plus_one_counters: int = 0
        self._base_minus_one_counters: int = 0
        self.damage_marked: int = 0
        self.summoning_sick: bool = True
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.is_token: bool = False
        self._is_animated: bool = False
        self._animate_trigger_registered: bool = False

    # ------------------------------------------------------------------
    # Continuous-effect reset support (P/T machinery for the animated land)
    # ------------------------------------------------------------------

    def _reset_characteristics(self) -> None:
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

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _colorless_effect(game: Any) -> None:
            ctrl = source.controller
            if ctrl is not None:
                ctrl.mana_pool.add(ManaType.COLORLESS, 1)

        def _any_color_cost(game: Any, src: Any) -> bool:
            # {T}, Pay 1 life.
            if getattr(src, "is_tapped", False):
                return False
            ctrl = getattr(src, "controller", None)
            if ctrl is None:
                return False
            src.is_tapped = True
            ctrl.life -= 1
            return True

        def _any_color_effect(game: Any) -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            # ENGINE LIMITATION: the "spend only on an instant/sorcery"
            # restriction cannot be enforced by the mana pool; the color is
            # added as ordinary mana.
            color = ctrl.choose(list(_ANY_COLOR_MANA), "color of mana to add")
            if color not in _ANY_COLOR_MANA:
                color = ManaType.WHITE
            ctrl.mana_pool.add(color, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_colorless_effect,
                description="{T}: Add {C}.",
            ),
            ManaAbility(
                cost=_any_color_cost,
                mana_produced=_any_color_effect,
                description="{T}, Pay 1 life: Add one mana of any color.",
            ),
        ]

    # ------------------------------------------------------------------
    # {5}: animate into a 2/4 Wizard creature (still a land)
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            from engine.types import ManaCost

            ctrl = getattr(src, "controller", None)
            if ctrl is None:
                return False
            return ctrl.mana_pool.pay(ManaCost.parse("{5}"))

        def _effect(game: Any) -> None:
            source._animate(game)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                description=(
                    "{5}: If this land isn't a creature, it becomes a 2/4 "
                    "Wizard creature. It's still a land."
                ),
            )
        ]

    def _animate(self, game: "GameState") -> None:
        """Turn this land into a 2/4 Wizard creature (still a land)."""
        if self._is_animated or CardType.CREATURE in self.card_types:
            return
        self._is_animated = True
        self.base_power = 2
        self.base_toughness = 4
        self.modified_power = 2
        self.modified_toughness = 4
        self.summoning_sick = True
        self.card_types = set(self.card_types) | {CardType.CREATURE}
        # Keep CREATURE through continuous-effect resets — this is a permanent
        # type change, not an until-end-of-turn effect.
        self._original_card_types = frozenset(
            self._original_card_types | {CardType.CREATURE}
        )
        self.subtypes = set(self.subtypes) | {"Wizard"}
        self._register_animate_trigger(game)

    def _register_animate_trigger(self, game: "GameState") -> None:
        if self._animate_trigger_registered:
            return
        self._animate_trigger_registered = True

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
            if CardType.CREATURE not in getattr(source, "card_types", set()):
                return False
            card = getattr(event, "card", None)
            if card is None:
                return False
            types = getattr(card, "card_types", set())
            if CardType.INSTANT not in types and CardType.SORCERY not in types:
                return False
            return getattr(event, "controller", None) is source.controller

        def _effect(game: Any) -> None:
            def _apply_buff(game: Any) -> None:
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
